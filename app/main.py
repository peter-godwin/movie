from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from app.routers import health, movie, auth
from app.db import connect_db, disconnect_db, AsyncSessionLocal
from app.schemas.base import ErrorResponse
from app.services.vector_service import vector_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    # Index movies for local "free" recognition
    # async with AsyncSessionLocal() as db:
    #     await vector_service.index_movies(db)
    yield
    await disconnect_db()


app = FastAPI(
    title="Moviz API",
    lifespan=lifespan,
)



@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            message=str(exc.detail)
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {
            "field": " -> ".join(str(loc) for loc in err["loc"] if loc != "body"),
            "message": err["msg"].replace("Value error, ", ""),
        }
        for err in exc.errors()
    ]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            message="Validation error",
            details=errors,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            message="An unexpected error occurred. Please try again later.",
            details=str(exc) if app.debug else None,
        ).model_dump(),
    )


app.include_router(health.router)
app.include_router(movie.router)
app.include_router(auth.router)