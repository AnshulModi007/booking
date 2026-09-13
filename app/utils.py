from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def password_hash(password: str):
    return pwd_context.hash(password)

def password_verify(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)