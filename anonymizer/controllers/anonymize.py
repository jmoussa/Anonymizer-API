from anonymizer.mongodb import get_nosql_db
from anonymizer.config import MONGODB_DB_NAME, SECRET_KEY_1, SECRET_KEY_2, SALT
from anonymizer.controllers.users import get_password_hash, verify_password
from anonymizer.controllers.utils import _encrypt, hash_dict_values, convert_object_ids
import logging

logger = logging.getLogger(__name__)


async def deanonymize_data(username, password):
    client = await get_nosql_db()
    db = client[MONGODB_DB_NAME]
    user_coll = db.users
    usersen_coll = db.usersen
    hashed_username = _encrypt(username, key=SECRET_KEY_1)
    logger.warning("Finding anonymized entry")
    row = user_coll.find_one({"username": hashed_username})
    row = convert_object_ids(row)

    if verify_password(password + SALT, row["password"]):
        signature = _encrypt(row["_id"], key=SECRET_KEY_2)
        usersen_row = usersen_coll.find_one({"root_id": signature})
        usersen_row = convert_object_ids(usersen_row)
        logger.warning(f"RETURN: {usersen_row}")
        return usersen_row
    else:
        logger.error("Incorrect password")
        return None


async def anonymize_data(username, password, _data):
    client = await get_nosql_db()
    db = client[MONGODB_DB_NAME]
    _collection = db.users
    data = {}
    hashed_username = _encrypt(username, key=SECRET_KEY_1)
    hashed_password = get_password_hash(password + SALT)
    data["username"] = hashed_username
    data["password"] = hashed_password
    for k, v in _data.items():
        if type(v) is str and "hashed:" in k:
            signature = _encrypt(v, key=SECRET_KEY_1)
            data[k] = signature
        elif type(v) is dict:
            copy_of_v = v.copy()
            data[k] = hash_dict_values(copy_of_v)
        else:
            data[k] = v

    # insert anonymized data
    inserted_anon_id = _collection.insert_one(data).inserted_id
    # use anon record's id to craft the "root_id" of the other entry
    signature = _encrypt(str(inserted_anon_id), key=SECRET_KEY_2)
    # insert into the sensitive info table
    _sensitive = db.usersen
    _sensitive.insert_one({"root_id": signature, "content": {**_data}})

    # return anonymized record
    row = _collection.find_one({"username": hashed_username})
    row = convert_object_ids(row)
    return row
