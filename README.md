# 🌟 Chiss - NASA Exoplanet Discovery Dashboard

**An AI-powered exoplanet detection and analysis platform built for NASA's Space Apps Challenge**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-green.svg)](https://www.docker.com/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Node 18+](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)

---

## 🚀 Quick Start (One Command!)

```bash
git clone https://github.com/seansimms/NASA_Chiss.git
cd NASA_Chiss
./START_DEMO.sh
```

**That's it!** The dashboard will open at **http://localhost:5173**

### Requirements
- Docker Desktop installed and running
- 4GB RAM available
- ~5 minutes for first-time setup

---

## 🎯 What is Chiss?

Chiss is an end-to-end machine learning pipeline for discovering exoplanets in NASA Kepler/TESS light curve data. It features:

- **🔍 Multi-Sector Search**: Analyze multiple observation sectors simultaneously
- **📊 Real-Time Monitoring**: Live job status, logs, and metrics
- **🤖 ML-Powered Detection**: Advanced transit detection algorithms
- **📈 Interactive Visualizations**: Phase-folded light curves, reliability plots
- **🎨 Modern UI**: Beautiful, responsive dashboard built with React + Vite

---

## 🌐 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React)                    │
│  Components: Discoveries, Workbench, Metrics, Alerts    │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP/WebSocket
┌─────────────────────┴───────────────────────────────────┐
│                  Backend (FastAPI)                      │
│  • Job Orchestrator  • WebSocket Logs                   │
│  • SQLite Database   • Real-time Metrics                │
│  • Multi-Sector Search                                  │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────┐
│              NASA Data Sources (MAST)                   │
│  Kepler, TESS, K2 Light Curves                          │
└─────────────────────────────────────────────────────────┘
```

---

## 📋 Features

### 🔬 Discovery Pipeline
- **Multi-Sector Search**: Combine data from multiple observation sectors
- **Transit Detection**: Find periodic dips in stellar brightness
- **Period Range Analysis**: Customizable period search ranges (1-1000 days)
- **Real-Time Logs**: Watch the analysis happen live via WebSocket

### 📊 Dashboard Tabs

#### 🌟 Discoveries
- Search by TIC ID (TESS Input Catalog)
- Configurable period ranges
- Live job monitoring
- Artifact downloads (light curves, phase plots, reports)

#### 🔧 Workbench
- Interactive light curve viewer
- Phase-folded transit plots
- Odd/Even transit comparison
- Centroid analysis

#### 📈 Reliability
- Model calibration curves
- Precision-Recall analysis
- ECE (Expected Calibration Error) plots
- Uncertainty quantification

#### ⚖️ Compare
- Benchmark against known planets
- Performance metrics (Precision, Recall, F1)
- Catalog comparisons (EU, NASA, Confirmed planets)

#### 🚨 Alerts
- Real-time event notifications
- Configurable alert rules
- Alert history and management

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Database ORM
- **Uvicorn** - ASGI server
- **WebSockets** - Real-time communication
- **Pandas/NumPy** - Data processing
- **Scikit-learn** - Machine learning

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool & dev server
- **TypeScript** - Type-safe JavaScript
- **Plotly.js** - Interactive visualizations
- **Modern CSS** - Responsive design

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Frontend serving (production)

---

## 📖 Detailed Usage

### Running a Multi-Sector Search

1. **Start the Dashboard**
   ```bash
   ./START_DEMO.sh
   ```

2. **Open Browser**
   Navigate to http://localhost:5173

3. **Go to Discoveries Tab**
   Click the "🌟 Discoveries" tab

4. **Enter Target Parameters**
   - **TIC ID**: `307210830` (example: known multi-planet system)
   - **Min Period**: `20` days
   - **Max Period**: `100` days

5. **Start Search**
   Click "Start Search" button

6. **Monitor Progress**
   - Watch live logs in real-time
   - See job status updates
   - Track queue position

7. **View Results**
   - Download artifacts when complete
   - Explore phase-folded light curves
   - Review candidate reports

### Example TIC IDs to Try

| TIC ID | Description | Period Range |
|--------|-------------|--------------|
| 307210830 | TOI-270 (3 confirmed planets) | 5-50 days |
| 260647166 | TOI-175 (multi-planet) | 10-100 days |
| 55525572 | Single transit candidate | 50-500 days |

---

## 🐳 Docker Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

### Restart Services
```bash
# Restart everything
docker-compose restart

# Restart backend only
docker-compose restart backend
```

### Stop Dashboard
```bash
./STOP_DEMO.sh
# or
docker-compose down
```

### Rebuild (after code changes)
```bash
docker-compose up --build
```

---

## 🔧 Development Setup

### Local Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export PORT=8001
export AUTH_REQUIRED=false
export ALLOWED_ORIGINS="http://localhost:5173"
export DB_PATH="./chiss.db"

# Run
python -m uvicorn app.main:app --reload --port 8001
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 📊 API Documentation

Once running, visit:
- **Interactive API Docs**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/api/health

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/jobs` | List all jobs |
| POST | `/api/jobs` | Create new job |
| GET | `/api/jobs/{id}/logs` | WebSocket for live logs |
| POST | `/api/jobs/{id}/cancel` | Cancel running job |
| GET | `/api/orchestrator/stats` | Queue stats |
| DELETE | `/api/jobs/clear` | Clear all jobs |

---

## 🎓 NASA Space Apps Challenge

This project was developed for the **NASA Space Apps Challenge** with the goal of making exoplanet discovery accessible and visual.

### Challenge Goals Met:
- ✅ Automated exoplanet detection from NASA data
- ✅ Real-time analysis dashboard
- ✅ Multi-sector data integration
- ✅ Interactive visualizations
- ✅ Open-source and reproducible
- ✅ Docker-based easy deployment

### Data Sources:
- **MAST (Mikulski Archive for Space Telescopes)**
  - Kepler light curves
  - TESS light curves
  - K2 mission data

---

## 🤝 Contributing

We welcome contributions! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **NASA** - For the incredible Kepler/TESS data
- **MAST Archive** - For data access and APIs
- **Lightkurve** - Python tools for Kepler/TESS data
- **Space Apps Challenge** - For the inspiration

---

## 📞 Support

- **Issues**: https://github.com/seansimms/NASA_Chiss/issues
- **Discussions**: https://github.com/seansimms/NASA_Chiss/discussions
- **Email**: seansimms00@gmail.com

---

## 🚀 Future Roadmap

- [ ] TESS-specific optimizations
- [ ] K2 mission support
- [ ] Real-time alert system for new discoveries
- [ ] Cloud deployment templates
- [ ] API authentication & rate limiting
- [ ] Batch processing for large surveys
- [ ] Machine learning model improvements
- [ ] Export to NASA Exoplanet Archive format

---

**Made with ❤️ for NASA Space Apps Challenge 2025**

**Happy Planet Hunting! 🌍🔭✨**

