from eqg.hashing import calculate_payload_hash, verify_payload_hash


def test_hash_is_stable_regardless_of_dictionary_key_order():
    left = {"z": 1, "a": {"second": 2, "first": 1}}
    right = {"a": {"first": 1, "second": 2}, "z": 1}
    assert calculate_payload_hash(left) == calculate_payload_hash(right)


def test_hash_detects_payload_modification():
    payload = {"restart_count": 3}
    digest = calculate_payload_hash(payload)
    assert verify_payload_hash(payload, digest)
    assert not verify_payload_hash({"restart_count": 4}, digest)


def test_hash_rejects_non_json_values():
    try:
        calculate_payload_hash({"bad": {1, 2}})
    except ValueError:
        pass
    else:
        raise AssertionError("Expected invalid JSON payload to raise ValueError")
