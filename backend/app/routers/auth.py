from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.models.models import User, Department, AuditLog
from app.schemas.schemas import Token, LoginRequest, UserResponse, DepartmentResponse
from app.core.security import verify_password, create_access_token, decode_token, oauth2_scheme

router = APIRouter(tags=["Authentication & Departments"])


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_role(allowed_roles: list):
    def role_checker(current_user: User = Depends(get_current_user)):
        user_role = (current_user.role or "").upper()
        allowed_upper = [r.upper() for r in allowed_roles]

        # Broad departmental mapping
        dept_roles = {"TRACK_ENGINEERING", "SIGNAL_TELECOM", "TRACTION_DISTRIBUTION", "DEPARTMENT_USER"}
        is_dept_user = user_role in dept_roles
        allowed_has_dept = any(r in dept_roles for r in allowed_upper)

        # Planner mapping
        is_planner = user_role in {"RAILWAY_PLANNER", "PLANNER"}
        allowed_has_planner = any(r in {"RAILWAY_PLANNER", "PLANNER"} for r in allowed_upper)

        # Admin mapping (admins have access everywhere)
        is_admin = user_role in {"SYSTEM_ADMIN", "ADMIN"}
        allowed_has_admin = any(r in {"SYSTEM_ADMIN", "ADMIN"} for r in allowed_upper)

        matched = (
            user_role in allowed_upper or
            (is_dept_user and allowed_has_dept) or
            (is_planner and allowed_has_planner) or
            (is_admin and allowed_has_admin)
        )

        if not matched:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {allowed_roles} roles. Your role is '{current_user.role}'."
            )
        return current_user
    return role_checker


@router.get("/departments", response_model=List[DepartmentResponse])
@router.get("/auth/departments", response_model=List[DepartmentResponse])
def get_departments(db: Session = Depends(get_db)):
    """
    Returns authoritative backend master departments for the common login dropdown.
    Includes Engineering, S&T, TRD / OHE, and Railway Planning & Operations.
    """
    return db.query(Department).filter(Department.is_active == True).order_by(Department.id).all()


@router.post("/auth/login", response_model=Token)
def login(login_req: LoginRequest, db: Session = Depends(get_db)):
    """
    Common Unified Department Login.
    Authenticates Official User ID and Security Password, and strictly validates selected Department.
    """
    user = db.query(User).filter(User.username == login_req.username.strip()).first()
    if not user or not verify_password(login_req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Validate Department selection if provided
    selected_dept = None
    if login_req.department:
        dept_query = login_req.department.strip()
        selected_dept = db.query(Department).filter(
            or_(
                Department.code.ilike(dept_query),
                Department.name.ilike(dept_query),
                Department.name.ilike(f"%{dept_query}%"),
                Department.code == dept_query.upper()
            )
        ).first()

        if not selected_dept:
            dq_low = dept_query.lower()
            if "plan" in dq_low or "operat" in dq_low or "traffic" in dq_low:
                selected_dept = db.query(Department).filter(Department.code == "OPERATIONS").first()
            elif "engg" in dq_low or "track" in dq_low or "civil" in dq_low or "engineering" in dq_low:
                selected_dept = db.query(Department).filter(Department.code == "ENGG").first()
            elif "signal" in dq_low or "snt" in dq_low or "telecom" in dq_low or "s&t" in dq_low:
                selected_dept = db.query(Department).filter(Department.code == "SNT").first()
            elif "trd" in dq_low or "ohe" in dq_low or "electr" in dq_low or "traction" in dq_low:
                selected_dept = db.query(Department).filter(Department.code == "TRD").first()

        if not selected_dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Selected department '{login_req.department}' is not recognized by backend master data."
            )

        # Verify department user belongs to selected department if specified
        dept_roles = {"TRACK_ENGINEERING", "SIGNAL_TELECOM", "TRACTION_DISTRIBUTION", "DEPARTMENT_USER", "department_user"}
        if user.role in dept_roles or user.role.upper() in dept_roles:
            if user.department_id and user.department_id != selected_dept.id:
                user_dept_name = user.department.name if user.department else "their assigned department"
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Authorization Mismatch: Official '{user.username}' is assigned to '{user_dept_name}', not '{selected_dept.name}'."
                )

    dept_code = selected_dept.code if selected_dept else (user.department.code if user.department else "OPERATIONS")
    dept_name = selected_dept.name if selected_dept else (user.department.name if user.department else "Railway Operations")

    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        department_code=dept_code
    )

    # Log to audit log
    audit = AuditLog(
        user_id=user.id,
        action="USER_LOGIN",
        entity_type="USER",
        entity_id=str(user.id),
        details_json={"username": user.username, "role": user.role, "department": dept_name, "department_code": dept_code}
    )
    db.add(audit)
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "department": dept_name,
            "department_id": selected_dept.id if selected_dept else user.department_id,
            "department_code": dept_code,
            "department_name": dept_name
        }
    }


@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
