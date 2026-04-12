import jwt, datetime

token = jwt.encode(
    {
        "sub": "alice",
        "iss": "DEFAULT-ISSUER",
        "aud": "DEFAULT-AUDIENCE",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    },
    key="DEFAULT-SECRET-KEY",
    algorithm="HS256",
)
print(token)