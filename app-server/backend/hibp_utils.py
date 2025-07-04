import requests, hashlib

def check_password_breach(password):
    # Hash the password using SHA-1
    sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix = sha1_hash[:5]
    suffix = sha1_hash[5:]

    # Query the HIBP API with the prefix
    url = f"https://api.pwnedpasswords.com/range/{prefix}"
    response = requests.get(url)

    if response.status_code != 200:
        raise RuntimeError("Error fetching data from HIBP")

    # Check if the suffix is in the returned hashes
    hashes = (line.split(":") for line in response.text.splitlines())
    for hash_suffix, count in hashes:
        if hash_suffix == suffix:
            return int(count)

    return 0