from fastapi import APIRouter, Depends, status
from fastapi.responses import HTMLResponse

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.auth.application.dto import LoginInput, LoginResult
from app.modules.auth.application.use_cases import (
    LoginUser,
    LoginWithGoogle,
    LogoutUser,
    RegisterAccount,
    RequestPasswordReset,
    ResendEmailVerification,
    ResetPassword,
    VerifyEmail,
)
from app.modules.auth.domain.entities import AuthSession, LoginPortal
from app.modules.auth.presentation.dependencies import (
    get_current_session,
    get_current_user,
    google_login_use_case,
    login_use_case,
    logout_use_case,
    register_account_use_case,
    request_password_reset_use_case,
    resend_email_verification_use_case,
    reset_password_use_case,
    verify_email_use_case,
)
from app.modules.auth.presentation.pages import reset_password_page, verify_email_page
from app.modules.auth.presentation.schemas import (
    AuthTokenResponse,
    EmailRequest,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.modules.users.application.dto import RegisterUserInput
from app.modules.users.domain.entities import User
from app.modules.users.presentation.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_payload(result: LoginResult) -> dict:
    return {
        "access_token": result.access_token.token,
        "expires_at": result.access_token.expires_at,
        "user": result.user,
    }


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[UserResponse],
    responses=error_responses(403, 409, 422),
)
def register(body: RegisterRequest, use_case: RegisterAccount = Depends(register_account_use_case)):
    user = use_case.execute(
        RegisterUserInput(
            name=body.name,
            email=body.email,
            password=body.password,
            role=body.role,
            phone_number=body.phone_number,
        )
    )
    return success_response("Registrasi berhasil, silakan cek email untuk verifikasi", user)


@router.post(
    "/login",
    response_model=ApiResponse[AuthTokenResponse],
    responses=error_responses(401, 403, 422),
)
def login(body: LoginRequest, use_case: LoginUser = Depends(login_use_case)):
    result = use_case.execute(LoginInput(email=body.email, password=body.password))
    return success_response("Login berhasil", _token_payload(result))


@router.post(
    "/google",
    response_model=ApiResponse[AuthTokenResponse],
    responses=error_responses(401, 403, 404, 422, 503),
)
def google_login(body: GoogleLoginRequest, use_case: LoginWithGoogle = Depends(google_login_use_case)):
    return success_response("Login berhasil", _token_payload(use_case.execute(body.id_token)))


@router.post(
    "/admin/login",
    response_model=ApiResponse[AuthTokenResponse],
    responses=error_responses(401, 403, 422),
)
def admin_login(body: LoginRequest, use_case: LoginUser = Depends(login_use_case)):
    result = use_case.execute(
        LoginInput(email=body.email, password=body.password, portal=LoginPortal.ADMIN_DASHBOARD)
    )
    return success_response("Login admin berhasil", _token_payload(result))


@router.get("/me", response_model=ApiResponse[UserResponse], responses=error_responses(401))
def me(current_user: User = Depends(get_current_user)):
    return success_response("Data akun berhasil diambil", current_user)


@router.post("/logout", response_model=ApiResponse[None], responses=error_responses(401))
def logout(
    session: AuthSession = Depends(get_current_session),
    use_case: LogoutUser = Depends(logout_use_case),
):
    use_case.execute(session)
    return success_response("Logout berhasil")


@router.get("/email/verify", response_class=HTMLResponse, include_in_schema=False)
def verify_email_form():
    return verify_email_page()


@router.post(
    "/email/verify",
    response_model=ApiResponse[None],
    responses=error_responses(400, 422),
)
def verify_email(body: VerifyEmailRequest, use_case: VerifyEmail = Depends(verify_email_use_case)):
    use_case.execute(body.token)
    return success_response("Email berhasil diverifikasi, silakan login")


@router.post("/email/resend", response_model=ApiResponse[None], responses=error_responses(422))
def resend_email_verification(
    body: EmailRequest,
    use_case: ResendEmailVerification = Depends(resend_email_verification_use_case),
):
    use_case.execute(body.email)
    return success_response("Jika email perlu diverifikasi, tautan baru sudah dikirim")


@router.post("/password/forgot", response_model=ApiResponse[None], responses=error_responses(422))
def forgot_password(
    body: EmailRequest,
    use_case: RequestPasswordReset = Depends(request_password_reset_use_case),
):
    use_case.execute(body.email)
    return success_response("Jika email terdaftar, tautan reset sudah dikirim")


@router.get("/password/reset", response_class=HTMLResponse, include_in_schema=False)
def reset_password_form():
    return reset_password_page()


@router.post(
    "/password/reset",
    response_model=ApiResponse[None],
    responses=error_responses(400, 422),
)
def reset_password(
    body: ResetPasswordRequest,
    use_case: ResetPassword = Depends(reset_password_use_case),
):
    use_case.execute(body.token, body.password)
    return success_response("Kata sandi berhasil diubah, silakan login")
