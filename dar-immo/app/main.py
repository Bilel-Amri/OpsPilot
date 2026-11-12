
"""Dar. — MVP immobilier, FastAPI + PostgreSQL."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
UPLOAD_DIR = STATIC / "uploads"

# Adresse de connexion fournie par l'environnement.
# Dans Kubernetes, elle sera construite avec le Service postgres.
DATABASE_URL = os.getenv("DATABASE_URL")

MAX_UPLOAD = 8 * 1024 * 1024

AMENITIES = {
    "Balcon", "Terrasse", "Parking", "Jardin", "Piscine",
    "Ascenseur", "Climatisation", "Meublé", "Vue mer", "Gardien",
}

Transaction = Literal["vente", "location"]
PropertyType = Literal["appartement", "maison", "terrain", "bureau"]


@contextmanager
def connection():
    """Ouvre une connexion PostgreSQL et gère commit/rollback."""
    if not DATABASE_URL:
        raise RuntimeError(
            "La variable d'environnement DATABASE_URL n'est pas configurée."
        )

    conn = psycopg.connect(
        DATABASE_URL,
        connect_timeout=10,
        row_factory=dict_row,
    )

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database():
    """Crée les tables et insère les annonces de démonstration."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                transaction_type TEXT NOT NULL
                    CHECK (transaction_type IN ('vente', 'location')),
                property_type TEXT NOT NULL
                    CHECK (property_type IN (
                        'appartement', 'maison', 'terrain', 'bureau'
                    )),
                price DOUBLE PRECISION NOT NULL CHECK (price > 0),
                city TEXT NOT NULL,
                district TEXT NOT NULL DEFAULT '',
                surface DOUBLE PRECISION NOT NULL CHECK (surface > 0),
                rooms INTEGER NOT NULL CHECK (rooms >= 0),
                bedrooms INTEGER NOT NULL CHECK (bedrooms >= 0),
                contact_name TEXT NOT NULL,
                contact_email TEXT NOT NULL DEFAULT '',
                contact_phone TEXT NOT NULL DEFAULT '',
                images TEXT NOT NULL DEFAULT '[]',
                amenities TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_demo BOOLEAN NOT NULL DEFAULT FALSE,
                edit_token_hash TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_listings_filters
            ON listings(transaction_type, property_type, price)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_listings_created
            ON listings(created_at DESC)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        already_seeded = conn.execute(
            "SELECT 1 FROM metadata WHERE key = %s",
            ("demo_seeded",),
        ).fetchone()

        if (
            not already_seeded
            and os.getenv("DAR_SEED_DEMO", "true").lower()
            in {"true", "1", "yes"}
        ):
            from .seed import demo_listings

            for item in demo_listings():
                insert_listing(conn, item, is_demo=True)

            conn.execute("""
                INSERT INTO metadata (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value
            """, ("demo_seeded", "1"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Dar. — API immobilière",
    description=(
        "MVP : annonces de vente et de location, recherche, photos "
        "et modification par clé secrète. "
        "Les annonces de démonstration sont fictives."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


class ListingInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=20, max_length=6000)
    transaction_type: Transaction
    property_type: PropertyType
    price: float = Field(
        gt=0, le=1_000_000_000_000, allow_inf_nan=False
    )
    city: str = Field(min_length=2, max_length=80)
    district: str = Field(default="", max_length=100)
    surface: float = Field(
        gt=0, le=10_000_000, allow_inf_nan=False
    )
    rooms: int = Field(default=1, ge=0, le=100)
    bedrooms: int = Field(default=0, ge=0, le=100)
    contact_name: str = Field(min_length=2, max_length=80)
    contact_email: str = Field(default="", max_length=254)
    contact_phone: str = Field(default="", max_length=35)
    images: list[str] = Field(default_factory=list, max_length=6)
    amenities: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if value and not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", value
        ):
            raise ValueError("L’adresse e-mail n’est pas valide.")
        return value

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if value and (
            not re.fullmatch(r"[+\d\s().-]+", value)
            or not 6 <= len(re.sub(r"\D", "", value)) <= 20
        ):
            raise ValueError("Le numéro de téléphone n’est pas valide.")
        return value

    @field_validator("images")
    @classmethod
    def validate_images(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(
                r"/static/(uploads/[a-f0-9]{32}\.jpg|images/[a-z0-9_-]+\.(?:jpg|png|webp))",
                value,
            ):
                raise ValueError(
                    "Veuillez téléverser vos photos via /api/uploads."
                )

            if not (
                STATIC / value.removeprefix("/static/")
            ).is_file():
                raise ValueError(
                    "Cette photo est introuvable. "
                    "Veuillez la téléverser à nouveau."
                )

        return list(dict.fromkeys(values))

    @field_validator("amenities")
    @classmethod
    def validate_amenities(cls, values: list[str]) -> list[str]:
        if not set(values).issubset(AMENITIES):
            raise ValueError("Un équipement n’est pas reconnu.")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.contact_email and not self.contact_phone:
            raise ValueError(
                "Renseignez un e-mail ou un numéro de téléphone "
                "pour être contacté."
            )

        if self.bedrooms > self.rooms:
            raise ValueError(
                "Le nombre de chambres ne peut pas dépasser "
                "le nombre de pièces."
            )

        return self


class ListingPublic(BaseModel):
    id: str
    title: str
    description: str
    transaction_type: Transaction
    property_type: PropertyType
    price: float
    city: str
    district: str
    surface: float
    rooms: int
    bedrooms: int
    contact_name: str
    contact_email: str
    contact_phone: str
    images: list[str]
    amenities: list[str]
    created_at: str
    updated_at: str
    is_demo: bool


class ListingPage(BaseModel):
    items: list[ListingPublic]
    total: int
    limit: int
    offset: int


class CreatedListing(BaseModel):
    listing: ListingPublic
    edit_token: str = Field(
        description=(
            "Clé secrète affichée une seule fois. "
            "À fournir dans X-Edit-Token pour modifier "
            "ou supprimer l’annonce."
        )
    )


def public_listing(row) -> dict:
    result = dict(row)
    result.pop("edit_token_hash", None)
    result["images"] = json.loads(result["images"])
    result["amenities"] = json.loads(result["amenities"])
    result["is_demo"] = bool(result["is_demo"])
    return result


def insert_listing(conn, data: dict, is_demo: bool = False):
    item = dict(data)

    item.setdefault("id", uuid4().hex[:16])

    now = datetime.now(timezone.utc).isoformat()
    item.setdefault("created_at", now)
    item.setdefault("updated_at", item["created_at"])

    item["is_demo"] = bool(is_demo)

    token = secrets.token_urlsafe(32)
    item["edit_token_hash"] = hashlib.sha256(
        token.encode()
    ).hexdigest()

    item["images"] = json.dumps(
        item.get("images", []), ensure_ascii=False
    )
    item["amenities"] = json.dumps(
        item.get("amenities", []), ensure_ascii=False
    )

    columns = ", ".join(item.keys())
    placeholders = ", ".join("%s" for _ in item)

    conn.execute(
        f"INSERT INTO listings ({columns}) VALUES ({placeholders})",
        list(item.values()),
    )

    return item["id"], token


def get_row(conn, listing_id: str):
    row = conn.execute(
        "SELECT * FROM listings WHERE id = %s",
        (listing_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Cette annonce est introuvable ou a été supprimée.",
        )

    return row


def check_owner(row, token: str | None):
    expected = row["edit_token_hash"]
    candidate = hashlib.sha256(
        (token or "").encode()
    ).hexdigest()

    if row["is_demo"] or not token or not hmac.compare_digest(
        expected, candidate
    ):
        raise HTTPException(
            status_code=403,
            detail="Clé de modification incorrecte ou manquante.",
        )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # Ne pas renvoyer l’intégralité des données saisies (coordonnées, etc.).
    errors = [
        {
            "loc": list(error["loc"]),
            "msg": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content={
            "message": "Vérifiez les informations saisies.",
            "detail": errors,
        },
    )


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = (
        "strict-origin-when-cross-origin"
    )

    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"

    return response


@app.get("/api/health", tags=["Système"])
def health():
    with connection() as conn:
        conn.execute("SELECT 1")

    return {
        "status": "ok",
        "app": "Dar.",
        "version": "1.0.0",
    }


@app.get("/api/stats", tags=["Annonces"])
def stats():
    with connection() as conn:
        counts = conn.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE transaction_type = 'vente'
                ) AS vente,
                COUNT(*) FILTER (
                    WHERE transaction_type = 'location'
                ) AS location,
                COUNT(DISTINCT city) AS cities,
                COUNT(*) FILTER (WHERE is_demo) AS demo
            FROM listings
        """).fetchone()

        cities = [
            row["city"]
            for row in conn.execute(
                "SELECT DISTINCT city FROM listings ORDER BY city"
            )
        ]

    return {
        **{key: counts[key] or 0 for key in counts.keys()},
        "city_names": cities,
    }


@app.get(
    "/api/listings",
    response_model=ListingPage,
    tags=["Annonces"],
)
def list_listings(
    q: str = Query(default="", max_length=120),
    city: str = Query(default="", max_length=80),
    transaction_type: Transaction | None = None,
    property_type: PropertyType | None = None,
    min_price: float | None = Query(
        default=None, ge=0, le=1_000_000_000_000,
        allow_inf_nan=False,
    ),
    max_price: float | None = Query(
        default=None, ge=0, le=1_000_000_000_000,
        allow_inf_nan=False,
    ),
    min_surface: float | None = Query(
        default=None, ge=0, le=10_000_000,
        allow_inf_nan=False,
    ),
    min_rooms: int | None = Query(
        default=None, ge=0, le=100
    ),
    sort: Literal[
        "recent", "price_asc", "price_desc", "surface_desc"
    ] = "recent",
    ids: str | None = Query(default=None, max_length=3500),
    limit: int = Query(default=12, ge=1, le=60),
    offset: int = Query(default=0, ge=0),
):
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            422,
            "Le prix minimum ne peut pas dépasser le prix maximum.",
        )

    clauses = []
    values = []

    if q.strip():
        # ILIKE permet une recherche insensible à la casse.
        # Les caractères spéciaux LIKE sont échappés.
        search_text = (
            q.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        clauses.append(
            "title || ' ' || city || ' ' || district || ' ' || "
            "description ILIKE %s ESCAPE E'\\\\'"
        )
        values.append(f"%{search_text}%")

    if city.strip():
        clauses.append("city ILIKE %s")
        values.append(city.strip())

    for field, value in (
        ("transaction_type", transaction_type),
        ("property_type", property_type),
    ):
        if value:
            clauses.append(f"{field} = %s")
            values.append(value)

    for field, operation, value in (
        ("price", ">=", min_price),
        ("price", "<=", max_price),
        ("surface", ">=", min_surface),
        ("rooms", ">=", min_rooms),
    ):
        if value is not None:
            clauses.append(f"{field} {operation} %s")
            values.append(value)

    if ids is not None:
        requested_ids = [
            item.strip()
            for item in ids.split(",")
            if item.strip()
        ][:200]

        if not requested_ids:
            return {
                "items": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
            }

        placeholders = ", ".join("%s" for _ in requested_ids)
        clauses.append(f"id IN ({placeholders})")
        values.extend(requested_ids)

    where = (
        " WHERE " + " AND ".join(clauses)
        if clauses
        else ""
    )

    ordering = {
        "recent": "created_at DESC, id DESC",
        "price_asc": "price ASC, created_at DESC",
        "price_desc": "price DESC, created_at DESC",
        "surface_desc": "surface DESC, created_at DESC",
    }[sort]

    with connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS total FROM listings" + where,
            values,
        ).fetchone()["total"]

        rows = conn.execute(
            "SELECT * FROM listings"
            + where
            + " ORDER BY "
            + ordering
            + " LIMIT %s OFFSET %s",
            values + [limit, offset],
        ).fetchall()

    return {
        "items": [public_listing(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get(
    "/api/listings/{listing_id}",
    response_model=ListingPublic,
    tags=["Annonces"],
)
def listing_detail(listing_id: str):
    with connection() as conn:
        return public_listing(get_row(conn, listing_id))


@app.post(
    "/api/listings",
    response_model=CreatedListing,
    status_code=201,
    tags=["Annonces"],
)
def create_listing(data: ListingInput):
    with connection() as conn:
        listing_id, token = insert_listing(
            conn, data.model_dump()
        )
        listing = public_listing(get_row(conn, listing_id))

    return {
        "listing": listing,
        "edit_token": token,
    }


@app.put(
    "/api/listings/{listing_id}",
    response_model=ListingPublic,
    tags=["Annonces"],
)
def update_listing(
    listing_id: str,
    data: ListingInput,
    x_edit_token: Annotated[str | None, Header()] = None,
):
    with connection() as conn:
        row = get_row(conn, listing_id)
        check_owner(row, x_edit_token)

        item = data.model_dump()

        item["images"] = json.dumps(
            item["images"], ensure_ascii=False
        )
        item["amenities"] = json.dumps(
            item["amenities"], ensure_ascii=False
        )
        item["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        assignments = ", ".join(
            f"{field} = %s" for field in item
        )

        conn.execute(
            f"UPDATE listings SET {assignments} WHERE id = %s",
            list(item.values()) + [listing_id],
        )

        return public_listing(get_row(conn, listing_id))


@app.delete(
    "/api/listings/{listing_id}",
    status_code=204,
    tags=["Annonces"],
)
def delete_listing(
    listing_id: str,
    x_edit_token: Annotated[str | None, Header()] = None,
):
    with connection() as conn:
        row = get_row(conn, listing_id)
        check_owner(row, x_edit_token)

        conn.execute(
            "DELETE FROM listings WHERE id = %s",
            (listing_id,),
        )


@app.post(
    "/api/uploads",
    status_code=201,
    tags=["Photos"],
)
async def upload_photo(
    file: Annotated[
        UploadFile,
        File(
            description=(
                "JPEG, PNG ou WebP, 8 Mo maximum. "
                "Les métadonnées sont supprimées."
            )
        ),
    ],
):
    try:
        data = await file.read(MAX_UPLOAD + 1)
    finally:
        await file.close()

    if len(data) > MAX_UPLOAD:
        raise HTTPException(
            413,
            "La photo dépasse la limite de 8 Mo.",
        )

    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(
                    415,
                    "Choisissez une image JPEG, PNG ou WebP.",
                )

            if (
                source.width * source.height > 36_000_000
                or max(source.size) > 12000
            ):
                raise HTTPException(
                    413,
                    "La définition de cette photo est trop élevée.",
                )

            image = ImageOps.exif_transpose(source)
            image.thumbnail((1800, 1800))

            if (
                image.mode in {"RGBA", "LA"}
                or (
                    image.mode == "P"
                    and "transparency" in image.info
                )
            ):
                rgba = image.convert("RGBA")
                background = Image.new(
                    "RGB", rgba.size, "#f3f4ef"
                )
                background.paste(
                    rgba, mask=rgba.getchannel("A")
                )
                image = background
            else:
                image = image.convert("RGB")

            filename = uuid4().hex + ".jpg"
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

            image.save(
                UPLOAD_DIR / filename,
                "JPEG",
                quality=86,
                optimize=True,
            )

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        ValueError,
    ):
        raise HTTPException(
            415,
            "Ce fichier n’est pas une image valide.",
        ) from None

    return {"url": f"/static/uploads/{filename}"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(
        STATIC / "favicon.svg",
        media_type="image/svg+xml",
    )


app.mount(
    "/static",
    StaticFiles(directory=STATIC),
    name="static",
)
