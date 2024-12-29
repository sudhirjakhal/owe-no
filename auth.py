import jwt
from fastapi import HTTPException, status, Cookie
from passlib.context import CryptContext
from models import User
from services import get_db

class AuthenticationException(Exception):
    pass

class UserNotFoundException(Exception):
    pass


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_passsword(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_hashed_password(password):
    return pwd_context.hash(password)

def get_user(email: str):
    try:
        db = next(get_db())

        user_query = db.query(User).filter(User.email == email).first()

        if user_query:
            user_data = {
                "email": user_query.email,
                "first_name": user_query.first_name,
                "last_name": user_query.last_name,
                "full_name": user_query.first_name + " " + user_query.last_name,
                "role": user_query.role,
                "user_id": user_query.id,
                "password": user_query.password
            }
            return user_data
        return None
    except Exception as e:
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
def authenticate_user(email: str, password: str):
    
    user = get_user(email)
    if not user:
        return None
    if not verify_passsword(password, user.get("password")):
        return False
    
    return user

async def get_current_user(email: str = Cookie(default=None)):
    if email is None:
        raise AuthenticationException
    
    user = get_user(email)
    if user is None:
        raise UserNotFoundException
    
    return user