# Boston Bioprocess Backend API

FastAPI backend for fermentation data visualization platform with external PostgreSQL database.

## Quick Railway Deployment

1. **Deploy to Railway**:
   - Connect this repository: `https://github.com/KNeerajSai/bbpb`
   - Railway auto-detects Dockerfile

2. **Set Environment Variables** in Railway:
   ```
   BBPF_DATABASE_URL=postgresql+asyncpg://bbp_fermentation_db_user:bjVRMB6vcBiqDpESPiM1biJvEcGgQfTb@dpg-d482qcemcj7s73dn4os0-a.oregon-postgres.render.com/bbp_fermentation_db
   BBPF_CORS_ORIGINS=["https://bbp-frontend1.onrender.com","https://your-frontend.railway.app","http://localhost:3000"]
   BBPF_DEBUG=false
   BBPF_LOG_LEVEL=INFO
   BBPF_HOST=0.0.0.0
   BBPF_PORT=8000
   ```

3. **Deploy**: Railway builds and deploys automatically

## Features

- FastAPI with async/await architecture
- External Render PostgreSQL database
- Automatic API documentation
- File upload with validation
- Interactive data visualization endpoints
- Health checks and monitoring

## API Endpoints

- `GET /` - API status
- `GET /health` - Health check
- `POST /api/v1/upload/` - Upload CSV files
- `GET /api/v1/runs/` - List all runs
- `GET /api/v1/runs/{run_id}` - Get run details
- `DELETE /api/v1/runs/{run_id}` - Delete run
- `GET /api/v1/visualization/{run_id}/data` - Get visualization data
- `GET /docs` - Interactive API documentation

## Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**:
   ```bash
   export BBPF_DATABASE_URL="postgresql+asyncpg://bbp_fermentation_db_user:bjVRMB6vcBiqDpESPiM1biJvEcGgQfTb@dpg-d482qcemcj7s73dn4os0-a.oregon-postgres.render.com/bbp_fermentation_db"
   export BBPF_CORS_ORIGINS='["http://localhost:3000"]'
   ```

3. **Run server**:
   ```bash
   python main.py
   # Or
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Database

Uses external Render PostgreSQL database with:
- **Host**: dpg-d482qcemcj7s73dn4os0-a.oregon-postgres.render.com
- **Database**: bbp_fermentation_db
- **User**: bbp_fermentation_db_user
- **Always available** (no sleep on database)

## Architecture

- **FastAPI**: Async web framework
- **SQLAlchemy**: ORM with async support  
- **Pydantic v2**: Data validation
- **PostgreSQL**: External database
- **Docker**: Containerized deployment