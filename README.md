# 🏗️ Elevated RCC Water Tank Design Suite

[![CI](https://github.com/your-org/elevated-water-tank/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/elevated-water-tank/actions)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Professional-grade Streamlit application for the complete Working Stress Method (WSM)
> design of elevated RCC water tanks per Indian Standard codes.**

---

## 📋 Features

| Feature | Details |
|---------|---------|
| **Tank Types** | Circular · Rectangular · Intze |
| **Design Code** | IS 3370:2009 (Parts I–IV), IS 456:2000 |
| **Loads** | IS 875 Parts 1–3 (Dead/Live/Wind), IS 1893 Part 2:2016 (Seismic) |
| **Optimiser** | Auto-ranks all feasible types by cost/m³ capacity |
| **Auto-Redesign** | Revises parameters when initial design fails |
| **PDF Report** | Multi-page professional report with all calculations |
| **BBS** | Full Bar Bending Schedule with weight summary |
| **Estimate** | Abstract of cost per DSR 2023-24 rates |
| **Drawings** | Schematic elevation + plan with dimension lines & callouts |
| **CI/CD** | GitHub Actions – pytest + flake8 on Python 3.10/3.11/3.12 |

---

## 🏛️ IS Code Coverage

```
IS 3370 Part I   – General requirements; min grade M25; cover 45mm water face
IS 3370 Part II  – WSM permissible stresses; min. reinforcement 0.24%
IS 3370 Part IV  – Coefficient tables (cylindrical: Tables 8–12; rect: Tables 3–7)
IS 456:2000      – Column design (cl. 39); slabs; footings; torsion (cl. 41)
IS 875 Part 1    – Unit weight RCC = 25 kN/m³
IS 875 Part 3    – Wind: Vz = Vb·k1·k2·k3; pz = 0.6Vz²; Cf = 0.7
IS 1893 Part 2   – Two-mass model; impulsive + convective; VB = √(Vi²+Vc²)
SP 16:1980       – Design aids
```

---

## ⚡ Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/your-org/elevated-water-tank.git
cd elevated-water-tank
pip install -r requirements.txt
```

### 2. Run App
```bash
streamlit run app.py
```

### 3. Run Tests
```bash
pytest tests/ -v --cov=src
```

---

## 🗂️ Project Structure

```
elevated-water-tank/
│
├── app.py                       # Streamlit UI (7 tabs)
├── requirements.txt
├── README.md
│
├── src/
│   ├── design/
│   │   ├── base.py              # IS constants, stresses, bar utilities
│   │   ├── is3370_tables.py     # Digitised IS 3370 Pt IV tables + interpolation
│   │   ├── circular_tank.py     # Circular tank WSM design engine
│   │   ├── intze_tank.py        # Intze tank WSM design engine
│   │   ├── rectangular_tank.py  # Rectangular tank WSM design engine
│   │   ├── seismic.py           # IS 1893 Pt 2 two-mass model
│   │   └── optimizer.py         # Multi-type ranker + auto-redesign
│   │
│   ├── report/
│   │   └── pdf_report.py        # ReportLab multi-page PDF report
│   │
│   └── drawing/
│       └── tank_drawings.py     # Matplotlib schematics (elevation + plan)
│
├── tests/
│   └── test_design.py           # pytest: 40+ tests across all modules
│
└── .github/
    └── workflows/
        └── ci.yml               # GitHub Actions CI pipeline
```

---

## 🔬 Design Methodology

### Cylindrical Wall (IS 3370 Part IV)
```
Parameter:  k = H² / (D · t)
Hoop tension:  T = Ct × γw × H × R         [kN/m]
Bending moment: M = Cm × γw × H³           [kN·m/m]
Hoop steel:   Ast = T / σst,direct         [mm²/m]
Vert. steel:  Ast = M / (σst × j × d)      [mm²/m]
```

### Intze Tank – Key Principle
```
Outward thrust (cone): Hcone = Nφ,cone × cos α
Inward thrust (dome):  Hdome = Nφ,dome × sin θ₁
Net BRB force ≈ 0 → self-balancing system
```

### Seismic (IS 1893 Part 2)
```
mi = impulsive liquid mass (from IS 1893 Pt2 Table 1)
mc = convective liquid mass
Vi = Ah,i × (mi + ms) × g
Vc = Ah,c × mc × g
VB = √(Vi² + Vc²)
```

---

## 📸 Application Screenshots

> **Tab 1 – Optimisation**: Ranks all tank types by cost efficiency  
> **Tab 3 – Design Calcs**: Expandable component cards with IS clause references  
> **Tab 5 – BBS**: Full bar bending schedule with downloadable CSV  
> **Tab 7 – Drawings**: Elevation + plan schematics with reinforcement callouts

---

## 🧪 Test Coverage

| Module | Tests |
|--------|-------|
| `base.py` | Neutral axis, lever arm, bar selection, Ast calculations |
| `is3370_tables.py` | Coefficient interpolation, boundary conditions |
| `circular_tank.py` | Volume adequacy, component presence, BBS |
| `intze_tank.py` | Intze condition, torsion, cone angles |
| `rectangular_tank.py` | L/B geometry, wall coefficients |
| `seismic.py` | Zone factors, base shear, spectral Sa/g |
| `optimizer.py` | Type ranking, cost ordering |

---

## 📦 Dependencies

| Package | Use |
|---------|-----|
| `streamlit` | Web UI |
| `pandas` | Data tables |
| `numpy` | Numerical arrays |
| `scipy` | IS 3370 coefficient interpolation |
| `matplotlib` | Schematic drawings, charts |
| `reportlab` | Professional PDF report |

---

## 📖 References

1. IS 3370 (Parts I–IV):2009 – BIS, New Delhi
2. IS 456:2000 – Plain & Reinforced Concrete
3. IS 875 (Part 3):2015 – Wind Loads
4. IS 1893 (Part 2):2016 – Seismic Design of Liquid Retaining Tanks
5. SP 16:1980 – Design Aids for RC to IS 456
6. N. Krishnaraju – *Advanced Reinforced Concrete Design*
7. B.C. Punmia et al. – *R.C.C. Designs*

---

## 👤 Author

**Daipayan Mandal**  
Assistant Professor, Department of Civil Engineering  
Kavikulguru Institute of Technology & Science (KITS), Ramtek  
Nagpur – 441106, Maharashtra, India  
*(Affiliated to RTMNU, Nagpur)*

---

## 📄 License

MIT License – see [LICENSE](LICENSE) for details.  
*For engineering use only. Independent verification is recommended for all designs.*
