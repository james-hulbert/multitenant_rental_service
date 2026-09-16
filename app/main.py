from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional
import os
import stripe
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict

from app.database import (
    create_tables,
    insert_tenant,
    get_all_tenants,
    insert_sample_user,
    get_all_users,
    get_user_by_id,
    insert_equipment,
    get_all_equipment,
    get_equipment_by_id_and_tenant,
    update_equipment_db,
    batch_archive_equipment,
    get_all_reservations,
    check_reservation_overlap,
    insert_reservation,
    update_reservation_db,
    update_reservation_payment_status,
    get_user_by_email,
    verify_password,
)
from app.models import TenantCreate, UserCreate, EquipmentCreate, ReservationCreate

# --- LIFESPAN EVENT HANDLER --- #
async def lifespan(app: FastAPI):
    #Startup actions
    create_tables()
    yield
    #Cleanup/Shutdown actions (if needed later)

# --- CONFIGURATION & SECURITY SETUP ---
stripe.api_key = os.getenv("STRIPE_API_KEY", "sk_test_51MockStripeKeyForDevelopment")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Initialize security scheme
oauth2_scheme = HTTPBearer()

app = FastAPI(
    title="Multi-Tenant Equipment Reservation System",
    version="1.0.0"
)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)):
    """Decodes the JWT token from the authorization header and extracts tenant/user scope."""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        tenant_id: int = payload.get("tenant_id")
        if email is None or tenant_id is None:
            raise credentials_exception
        return {"email": email, "tenant_id": tenant_id}
    except JWTError:
        raise credentials_exception


from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import create_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: runs when the application starts
    create_tables()
    yield
    # Shutdown logic: (optional) cleanup actions go here

app = FastAPI(
    title="Equipment Rental API",
    lifespan=lifespan
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Multi-Tenant Equipment Reservation API"}


# --- AUTHENTICATION ENDPOINT ---

class LoginRequest(BaseModel):
    tenant_id: int
    email: str
    password: str


@app.post("/token")
def login_for_access_token(payload: LoginRequest):
    """Authenticate user credentials and return a secure JWT access token."""
    user = get_user_by_email(payload.email, payload.tenant_id)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password, or invalid tenant.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user["email"], "tenant_id": user["tenant_id"], "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": encoded_jwt, "token_type": "bearer"}


# --- TENANT ENDPOINTS ---

@app.get("/tenants")
def list_tenants():
    """Fetch all onboarded tenant accounts."""
    return {"tenants": get_all_tenants()}


@app.post("/tenants", status_code=status.HTTP_201_CREATED)
def create_tenant(tenant: TenantCreate):
    """Onboard a new rental business account."""
    new_tenant = insert_tenant(name=tenant.name)
    if not new_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant with name '{tenant.name}' already exists."
        )
    return new_tenant


# --- USER ENDPOINTS ---

@app.get("/users")
def list_users():
    """Fetch all users across tenants."""
    return {"users": get_all_users()}


@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    """Create a new user scoped to a specific tenant_id."""
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    password_str = getattr(user, "password", "secretpassword")
    new_user = insert_sample_user(
        tenant_id=user.tenant_id,
        email=user.email,
        password=password_str,
        role=role_str
    )
    if not new_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{user.email}' already exists for this tenant."
        )
    return new_user


# --- EQUIPMENT ENDPOINTS ---

class EquipmentResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    description: Optional[str] = None
    daily_rate: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EquipmentUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    daily_rate: float
    status: str


class EquipmentBatchArchive(BaseModel):
    equipment_ids: list[int]


@app.get("/equipment", response_model=list[EquipmentResponse])
def list_equipment(current_user: dict = Depends(get_current_user)):
    """Retrieve all equipment items for the authenticated user's tenant."""
    return get_all_equipment(current_user["tenant_id"])


@app.post("/equipment", status_code=status.HTTP_201_CREATED, response_model=EquipmentResponse)
def create_equipment_item(item: EquipmentCreate, current_user: dict = Depends(get_current_user)):
    """Create a new equipment item securely scoped to the authenticated tenant."""
    new_item = insert_equipment(
        tenant_id=current_user["tenant_id"],
        name=item.name,
        description=item.description,
        daily_rate=item.daily_rate,
        status=item.status.value if hasattr(item.status, "value") else str(item.status),
    )
    if not new_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create new equipment item.")
    return new_item


@app.put("/equipment/batch-archive", response_model=list[EquipmentResponse])
def bulk_archive_equipment(payload: EquipmentBatchArchive, current_user: dict = Depends(get_current_user)):
    """Archive multiple equipment items simultaneously for the authenticated tenant."""
    return batch_archive_equipment(current_user["tenant_id"], payload.equipment_ids)


@app.put("/equipment/{equipment_id}", response_model=EquipmentResponse)
def update_equipment(equipment_id: int, payload: EquipmentUpdate, current_user: dict = Depends(get_current_user)):
    """Update an existing equipment item belonging to the authenticated tenant."""
    updated = update_equipment_db(
        equipment_id=equipment_id,
        tenant_id=current_user["tenant_id"],
        name=payload.name,
        description=payload.description,
        daily_rate=payload.daily_rate,
        status=payload.status
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found or unauthorized.")
    return updated


# --- RESERVATION ENDPOINTS ---

class ReservationResponse(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    equipment_id: int
    start_date: datetime
    end_date: datetime
    total_cost: float
    payment_intent_id: Optional[str] = None
    payment_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReservationUpdate(BaseModel):
    start_date: datetime
    end_date: datetime
    total_cost: float
    payment_status: str


@app.get("/reservations", response_model=list[ReservationResponse])
def list_reservations(current_user: dict = Depends(get_current_user)):
    """Retrieve all reservations scoped to the authenticated tenant."""
    return get_all_reservations(current_user["tenant_id"])


@app.post("/reservations", status_code=status.HTTP_201_CREATED)
def create_reservation(payload: ReservationCreate, current_user: dict = Depends(get_current_user)):
    """Validate reservation, calculate cost, generate PaymentIntent, and store record."""
    # 1. Validate date logic
    if payload.end_date <= payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be strictly after start date."
        )

    # 2. Verify user exists within this tenant scope
    user = get_user_by_id(payload.user_id)
    if not user or user["tenant_id"] != current_user["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {payload.user_id} does not exist in this tenant."
        )

    # 3. Check if equipment exists strictly for the current user's tenant scope
    equipment = get_equipment_by_id_and_tenant(payload.equipment_id, current_user["tenant_id"])
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found for this tenant"
        )

    # 4. Check for reservation date overlap within the tenant scope
    if check_reservation_overlap(payload.equipment_id, payload.start_date, payload.end_date, current_user["tenant_id"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Equipment is already reserved for these dates"
        )

    # 5. Calculate duration and total cost
    duration = payload.end_date - payload.start_date
    days = max(1, duration.days)
    total_cost = days * float(equipment["daily_rate"])

    # 6. Generate payment intent mock
    class MockPaymentIntent:
        id = "pi_3MtwA2LkdIwHu7ix08a2Bmock"
        client_secret = "pi_3MtwA2LkdIwHu7ix08a2Bmock_secret_test123"

    payment_intent = MockPaymentIntent()

    # 7. Insert reservation
    new_reservation = insert_reservation(
        tenant_id=current_user["tenant_id"],
        user_id=payload.user_id,
        equipment_id=payload.equipment_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_cost=total_cost,
        payment_intent_id=payment_intent.id,
        payment_status="requires_payment_method"
    )

    return {
        "reservation": new_reservation,
        "client_secret": payment_intent.client_secret
    }


@app.put("/reservations/{reservation_id}", response_model=ReservationResponse)
def update_reservation(reservation_id: int, payload: ReservationUpdate, current_user: dict = Depends(get_current_user)):
    """Update an existing reservation's details for the authenticated tenant."""
    updated = update_reservation_db(
        reservation_id=reservation_id,
        tenant_id=current_user["tenant_id"],
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_cost=payload.total_cost,
        payment_status=payload.payment_status
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found or unauthorized.")
    return updated


# --- STRIPE WEBHOOK ENDPOINT ---

@app.post("/webhook")
async def stripe_webhook(request: Request):
    """Listen for incoming Stripe events and update reservation payment statuses."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET", None)

    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            data = await request.json()
            event = stripe.Event.construct_from(data, stripe.api_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid payload: {str(e)}")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid signature: {str(e)}")

    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        updated = update_reservation_payment_status(
            payment_intent_id=payment_intent["id"],
            new_status="succeeded"
        )
        if updated:
            print(f"✅ Successfully marked Reservation ID {updated['id']} as paid!")

    return {"status": "success"}