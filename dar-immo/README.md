# Dar. — MVP de petites annonces immobilières

Une version minimale **fonctionnelle**, avec **FastAPI**, **SQLite** et une interface web responsive en français. Sans framework JavaScript, sans compilation frontend et sans service payant.

## Démarrage rapide

Python **3.11 ou supérieur** requis avec les versions de dépendances fournies.

```bash
cd dar-immo
python -m venv .venv
source .venv/bin/activate       # Windows : .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Application : http://localhost:8000
- Documentation interactive Swagger : http://localhost:8000/docs
- Schéma OpenAPI : http://localhost:8000/openapi.json
- Vérification de fonctionnement : http://localhost:8000/api/health

L’interface utilise des URL relatives. L’API, les styles, les polices et les photos sont servis par la même application. Aucun CDN n’est nécessaire au fonctionnement.

## Ce qui est inclus

- Annonces **à vendre / à louer** : appartement, maison/villa, terrain et bureau.
- Recherche par ville, quartier ou mot-clé, insensible aux accents et à la casse.
- Filtres : type de bien, transaction, budget maximum, surface et nombre de pièces.
- Tri par date, prix ou surface ; pagination.
- Fiche détaillée, galerie de photos, équipements, coordonnées de l’annonceur et partage du lien.
- Publication, modification et suppression d’une annonce.
- Téléversement de 6 photos maximum, JPEG/PNG/WebP, 8 Mo par fichier. Réencodage en JPEG, réduction à 1 800 px et suppression des métadonnées EXIF.
- Favoris dans le navigateur (`localStorage`).
- Espace « Mes annonces » dans le même navigateur.
- Validation côté serveur, requêtes SQL paramétrées et clés de modification hachées en SHA-256.
- Tests automatisés de l’API.

### Hypothèses de cette version

- Interface en français, exemples de villes tunisiennes, prix en **dinars tunisiens (DT/TND)**.
- **Pas de compte utilisateur** : la création renvoie une clé secrète unique. Elle est enregistrée dans ce navigateur et permet de modifier ou supprimer uniquement son annonce.
- La clé peut être téléchargée immédiatement après publication. Elle n’est plus renvoyée ensuite. Une clé perdue ne peut pas être récupérée.
- Les coordonnées renseignées par l’annonceur sont publiques dans l’API et visibles sur la fiche après clic sur « Contacter l’annonceur ». Ne publiez pas de coordonnées confidentielles.
- Pas de paiement, de réservation, de carte, de messagerie interne ni d’envoi d’e-mails. Les boutons de contact ouvrent le téléphone ou la messagerie du visiteur.

## Annonces de démonstration

Au premier lancement, six annonces **entièrement fictives** sont créées. Leurs photos sont **illustratives** : elles ne représentent pas des biens réellement proposés à ces adresses. Les annonces sont marquées « DÉMO », sans coordonnées réelles, et ne peuvent pas être modifiées publiquement.

Pour partir d’une base vide :

```bash
DAR_SEED_DEMO=false uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Cette variable agit lors de l’initialisation d’une nouvelle base. Pour repartir de zéro, arrêtez le serveur, sauvegardez puis supprimez le fichier `data/dar.sqlite3` et ses éventuels fichiers `-wal` et `-shm`.

Les données sont conservées dans `data/dar.sqlite3`. Les photos téléversées sont stockées dans `app/static/uploads/`. Pour changer le chemin de la base :

```bash
DAR_DB_PATH=/chemin/persistant/dar.sqlite3 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Sous Windows PowerShell, définissez préalablement la variable avec `$env:DAR_SEED_DEMO="false"`.

## API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | État de l’application et accès à SQLite |
| GET | `/api/stats` | Nombre d’annonces et villes disponibles |
| GET | `/api/listings` | Recherche, filtres, tri et pagination |
| GET | `/api/listings/{id}` | Fiche publique |
| POST | `/api/listings` | Créer ; renvoie `listing` et `edit_token` |
| PUT | `/api/listings/{id}` | Modifier ; en-tête `X-Edit-Token` requis |
| DELETE | `/api/listings/{id}` | Supprimer ; en-tête `X-Edit-Token` requis |
| POST | `/api/uploads` | Téléverser une photo ; champ multipart `file` |

Exemple de recherche :

```bash
curl 'http://localhost:8000/api/listings?transaction_type=location&city=Tunis&max_price=2000&sort=price_asc'
```

Création :

```bash
curl -X POST http://localhost:8000/api/listings \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Appartement lumineux à Tunis",
    "description": "Un appartement lumineux avec balcon, proche des transports.",
    "transaction_type": "location",
    "property_type": "appartement",
    "price": 1500,
    "city": "Tunis",
    "district": "Centre-ville",
    "surface": 90,
    "rooms": 3,
    "bedrooms": 2,
    "contact_name": "Votre nom",
    "contact_email": "vous@example.com",
    "contact_phone": "",
    "images": [],
    "amenities": ["Balcon"]
  }'
```

Conservez l’`edit_token` de la réponse. Pour modifier, renvoyez l’objet complet avec `PUT` et cet en-tête. Pour supprimer :

```bash
curl -X DELETE 'http://localhost:8000/api/listings/ID_DE_VOTRE_ANNONCE' \
  -H 'X-Edit-Token: VOTRE_CLE_PRIVEE'
```

Un lien direct vers une annonce a la forme `/?annonce=ID`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Les tests isolent leurs bases et photos dans un dossier temporaire. Ils couvrent la création, la lecture, la recherche, les filtres, le tri, la pagination, les validations, les droits de modification/suppression, le téléversement, les statistiques et l’initialisation des exemples.

## Structure

```text
dar-immo/
├── app/
│   ├── main.py                 # API, validation, SQLite, photos
│   ├── seed.py                 # 6 annonces fictives
│   └── static/
│       ├── index.html          # Interface web
│       ├── styles.css          # Responsive, police locale
│       ├── app.js              # Recherche et interactions
│       ├── fonts/              # DM Sans et licence OFL
│       ├── images/             # Photos d’illustration locales
│       └── uploads/            # Photos ajoutées par les utilisateurs
├── data/                       # SQLite (créée au démarrage)
├── tests/test_api.py
├── requirements.txt
└── requirements-dev.txt
```

## Avant une mise en production

Ce projet est un **MVP**, pas une plateforme publique prête à grande échelle. Avant publication réelle, ajouter notamment :

- Comptes, récupération d’accès et vérification des coordonnées ; modération et signalement des annonces.
- Limitation des requêtes, quotas de publication/téléversement, protection anti-spam et limites de taille HTTP au niveau du reverse proxy. L’envoi de photos est public dans ce MVP.
- HTTPS, politique de confidentialité, conditions d’utilisation et procédures de retrait/suppression des données personnelles.
- Sauvegardes de la base **et** des photos, journaux, supervision et stockage persistant adapté au déploiement.
- Nettoyage périodique des photos orphelines : une photo téléversée puis abandonnée n’est pas automatiquement supprimée ici, et la suppression d’une annonce ne supprime pas son fichier image.
- PostgreSQL et stockage d’objets si le volume ou le nombre d’instances le justifie.

Les clés de modification ne sont pas des comptes : effacer le stockage du navigateur retire l’accès depuis l’interface. Une clé téléchargée permet toujours d’utiliser l’API sur l’annonce correspondante.

## Crédits visuels

Police **DM Sans**, licence SIL Open Font License incluse dans `app/static/fonts/OFL.txt`.

Photographies d’illustration : **Unsplash**, copies locales téléchargées pour ce prototype. Sources :

- https://images.unsplash.com/photo-1600596542815-ffad4c1539a9
- https://images.unsplash.com/photo-1600607687920-4e2a09cf159d
- https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea
- https://images.unsplash.com/photo-1600607687939-ce8a6c25118c
- https://images.unsplash.com/photo-1613490493576-7fde63acd811
- https://images.unsplash.com/photo-1600607688969-a5bfcd646154
- https://images.unsplash.com/photo-1600047509782-20d39509f26d

Les photos ne prouvent pas l’existence, la disponibilité ou la localisation des biens fictifs.
