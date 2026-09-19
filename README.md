# FinPilot: Personal Finance Decision Support Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B.svg)](https://streamlit.io/)

**FinPilot** is an AI-powered personal finance decision-support agent designed to help individuals gain clarity over everyday finances. Rather than acting as a traditional banking dashboard or investment advisory platform, FinPilot bridges the gap between raw transaction records and actionable financial decision-making.

FinPilot ingests, standardizes, and analyzes multi-source financial data to explain where money is going, anticipate upcoming obligations, flag unusual spending patterns, and quantify how daily decisions impact personal financial goals.

---

## 🚀 Core Capabilities

### 1. Data Ingestion & Intelligent Categorization
- **Multi-Format Ingestion**: Parsers for CSV, JSON, and PDF bank/credit card statements and utility bills.
- **Schema Normalizer**: Standardizes raw vendor descriptions, dates into ISO format (`YYYY-MM-DD`), and normalizes sign conventions (expenses negative, income positive).
- **Hybrid Categorization Engine**: Rule-based keyword/regex matching combined with context-aware fallbacks (`SQUARE * CAFE` $\rightarrow$ Dining Out, `NETFLIX` $\rightarrow$ Subscriptions, `CONED` $\rightarrow$ Utilities).

### 2. Pattern Recognition & Automated Detection
- **Subscription & Recurring Obligation Tracker**: Detects recurring transactions using interval frequencies (~30-day or annual cycles) and low price variance ($\le 5\%$).
- **Anomaly & Spike Detector**: Identifies vendor/category transactions exceeding $2.5\times$ historical standard deviation, as well as category month-over-month spending spikes ($>20\%$ MoM).
- **Committed Spend Ratio**: Calculates fixed obligations due prior to the next pay cycle to determine safe-to-spend balances.

### 3. Goal Modeling & Budget Tracking
- **Budget Variance Analysis**: Tracks real-time category spending against user-defined monthly budget caps.
- **Goal Simulation & Impact Analysis**: Deterministically projects completion timelines for targets based on net cash flow ($\text{Income} - \text{Expenses}$):
  $$\text{Months to Target Goal} = \frac{\text{Target Amount} - \text{Current Savings}}{\text{Monthly Net Cash Flow}}$$

### 4. Conversational Q&A & Executive Insights
- **Structured Query Execution**: Translates natural language questions (*"Where did I spend the most this month?"*, *"Which subscriptions am I paying for?"*, *"What expenses increased compared to last month?"*) into precise DuckDB SQL queries without LLM math hallucinations.
- **Monthly Brief Generator**: Produces executive monthly financial summaries containing key observations, budget status tables, anomaly flags, and actionable next steps.

---

## 🛠️ Architecture Blueprint

```
+-----------------------------------------------------------------------------------+
|                                 USER INTERFACE                                    |
|                             Streamlit Dashboard UI                                |
+------------------------------------------+----------------------------------------+
                                           |
                                 REST API / In-Memory Call
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                               BACKEND CORE AGENT                                  |
|                                                                                   |
|  +--------------------+    +--------------------+    +-------------------------+  |
|  | Ingestion Engine   |    | Core Analytics     |    | Goal & Budget Logic     |  |
|  | (CSV / JSON / PDF) |    | (Categorization &  |    | (Cash Flow, Safe-to-   |  |
|  |                    |    | Pattern Detection) |    | Spend, Forecasting)     |  |
|  +---------+----------+    +---------+----------+    +------------+------------+  |
|            |                         ^                            ^               |
|            v                         |                            |               |
|  +-----------------------------------+----------------------------+------------+  |
|  |                       LLM Conversational Router                             |  |
|  |             (Natural Language Queries, Safe DuckDB SQL Execution)           |  |
|  +-----------------------------------------------------------------------------+  |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                                DATABASE & STORAGE                                 |
|                             DuckDB Analytical Engine                              |
+-----------------------------------------------------------------------------------+
```

---

## 📦 Installation & Setup

1. **Clone Repository**:
   ```bash
   git clone https://github.com/229003021-spec/Fin_Pilot.git
   cd Fin_Pilot
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Interactive Dashboard**:
   ```bash
   streamlit run app.py
   ```

4. **Run Unit Tests**:
   ```bash
   python -m pytest
   ```

---

## ⚖️ Decision-Support Boundary & Guardrails

- **Deterministic Calculation First**: All sums, variances, standard deviations, and goal timelines are computed via DuckDB SQL and Python code execution prior to response presentation.
- **Decision-Support Boundary**: FinPilot explicitly clarifies that it provides data-driven decision support and not certified financial, investment, accounting, or legal tax advice.
- **Data Privacy**: Raw account credentials and full sensitive account identifiers are masked or omitted from agent outputs using privacy sanitization rules.

---

## 📄 License

Distributed under the MIT License.
