# Traffic Digital Twin: Infrastructure Engine

A geospatial analysis and simulation tool for urban traffic infrastructure planning. This tool allows users to draw road proposals on a map, analyze their feasibility (building collisions), and simulate their impact on traffic flow using a digital twin model.

## Features
- **Proposal Analyzer**: Compare multiple road designs based on connectivity and building impact.
- **Smart Suggestion**: AI-powered recommendations for infrastructure type (Flyover, Tunnel, Surface Road) based on geography.
- **Feasibility Engine**: Automated detection of building collisions and demolition requirements.
- **Digital Twin Simulation**: Stochastic traffic modeling to compare travel times before and after infrastructure changes.

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/SwathiHRao28/capstone.git
cd capstone
```

### 2. Create a Virtual Environment (Recommended)
```bash
python -m venv venv
```

**Activate it:**
- **Windows:** `venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

### 3. Install Dependencies
```bash
pip install -r traffic-infra-engine/requirements.txt
```

### 4. Run the Application
```bash
streamlit run traffic-infra-engine/app.py
```

## Project Structure
- `traffic-infra-engine/app.py`: Main Streamlit application.
- `traffic-infra-engine/feasibility_engine/`: Logic for collision detection.
- `traffic-infra-engine/graph_modification/`: Tools for network graph updates.
- `traffic-infra-engine/simulation_engine/`: Traffic flow simulation logic.
- `traffic-infra-engine/utils/`: Data loaders and helpers.
