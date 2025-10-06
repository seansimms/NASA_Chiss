# 🚀 NASA Judges - Quick Start Guide

**Get the Chiss Dashboard running in 5 minutes!**

---

## Prerequisites

Only one requirement:
- **Docker Desktop** installed and running
  - Mac: https://docs.docker.com/desktop/install/mac-install/
  - Windows: https://docs.docker.com/desktop/install/windows-install/
  - Linux: https://docs.docker.com/desktop/install/linux-install/

---

## Step-by-Step Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/seansimms/NASA_Chiss.git
cd NASA_Chiss
```

### 2. Start the Dashboard

```bash
./START_DEMO.sh
```

**That's it!** The script will:
- ✅ Check Docker is running
- ✅ Build containers (3-5 minutes first time)
- ✅ Start backend and frontend
- ✅ Wait for services to be healthy
- ✅ Show you the URL

### 3. Open in Browser

Navigate to:
```
http://localhost:5173
```

---

## 🎯 Try a Demo Search

1. **Click the "🌟 Discoveries" tab**

2. **Enter these parameters:**
   - TIC ID: `307210830` (TOI-270, a known 3-planet system)
   - Min Period: `5` days
   - Max Period: `50` days

3. **Click "Start Search"**

4. **Watch the magic:**
   - Live logs stream in real-time
   - Job status updates automatically
   - Results available when complete

---

## 🎬 Demo Script (3 minutes)

**"Hello! Let me show you Chiss, our exoplanet discovery platform..."**

### Minute 1: Overview
- "This is the Command Center - our real-time dashboard"
- "We can monitor jobs, view logs, and track the queue"
- "Let's search for exoplanets in a known system"

### Minute 2: Start Search
- Navigate to Discoveries tab
- Enter TIC 307210830
- "This is TOI-270, discovered by TESS"
- Click "Start Search"
- "Watch the logs - we're fetching data from NASA MAST"

### Minute 3: Features Tour
- Show the 5 tabs: Discoveries, Reliability, Compare, History, Alerts
- "The backend runs async jobs with WebSocket streaming"
- "We use Docker for easy deployment anywhere"
- "All data comes directly from NASA archives"

**"Questions?"**

---

## 🛠️ Troubleshooting

### "Docker not found"
➡️ Install Docker Desktop and restart terminal

### "Port 5173 already in use"
```bash
./STOP_DEMO.sh
./START_DEMO.sh
```

### "Backend not healthy"
```bash
docker-compose logs backend
```

### Need to restart everything?
```bash
./STOP_DEMO.sh
docker-compose down -v  # Remove volumes
./START_DEMO.sh
```

---

## 📊 Architecture at a Glance

```
Frontend (React + Vite)
    ↓ HTTP/WebSocket
Backend (FastAPI)
    ↓ SQL
SQLite Database
    ↓ API Calls
NASA MAST Archive
```

---

## 🌟 Key Features to Highlight

1. **Real-Time Logs** - WebSocket streaming of job output
2. **Multi-Sector** - Combines data from multiple observation periods
3. **Interactive Viz** - Phase-folded light curves, reliability plots
4. **Docker-Based** - One command to start everything
5. **NASA Data** - Direct integration with MAST archive

---

## 📞 Support

- **GitHub**: https://github.com/seansimms/NASA_Chiss
- **Issues**: https://github.com/seansimms/NASA_Chiss/issues
- **Email**: seansimms00@gmail.com

---

## 🎓 Additional Resources

- **Full README**: See `README.md` for complete documentation
- **API Docs**: http://localhost:8001/docs (when running)
- **Contributing**: See `CONTRIBUTING.md`

---

**Happy Planet Hunting! 🌍🔭✨**

---

**NASA Space Apps Challenge 2025**
*Making exoplanet discovery accessible to everyone*

