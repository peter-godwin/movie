# Moviz
A movie recognition app 

# Start server 
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run migration
alembic upgrade head
