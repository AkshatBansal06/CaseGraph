# CaseGraph 🕵️

**An interactive detective game where you investigate cases, interrogate people, uncover clues, connect evidence, and solve mysteries.**

CaseGraph is a detective investigation game built around a structured investigation system. Players work through case briefings, conduct interviews, validate investigative insights, uncover clues, connect evidence, reconstruct events, and ultimately make accusations.

Every investigation is driven by the information the player discovers and the connections they establish—not simply by selecting a suspect.

## 🎮 Gameplay

The game follows a progressive investigation loop:

1. **Case Briefing** — Begin with an incident report and understand the circumstances surrounding the case.
2. **Investigation** — Explore the case, interview characters, and gather information.
3. **Insight Validation** — Validate deductions to unlock additional clues and advance the investigation.
4. **Evidence Collection** — Discover and file evidence into the case.
5. **Relationship Analysis** — Connect people and evidence to uncover meaningful relationships.
6. **Timeline Reconstruction** — Build a chronological understanding of events.
7. **Accusation** — Use the information gathered to identify and accuse the responsible individual.
8. **Case Resolution** — Complete the investigation and receive a score based on your performance.

## 🧩 Core Mechanics

- **Interactive Investigations** — Progress through structured cases instead of passively reading a mystery.
- **Interviews** — Interact with characters to obtain information relevant to the investigation.
- **Insight-Based Progression** — Validate investigative insights to unlock clues and advance the case.
- **Evidence Filing** — Collect and record evidence as your investigation progresses.
- **Relationship Discovery** — Establish connections between people and investigative elements.
- **Timeline Analysis** — Reconstruct the sequence of events.
- **Deduction & Accusation** — Reach conclusions based on the information uncovered.
- **Scoring System** — Your investigation is evaluated upon case completion.

## 🔍 Investigation System

CaseGraph uses a connected investigation model in which cases, people, evidence, relationships, and events are stored and linked through a relational database.

These connections support the investigative gameplay, allowing information gathered during a case to become part of a larger picture.

The system combines game progression with database-backed persistence for investigation sessions, evidence, relationships, timeline events, and case outcomes.

## 🗂️ Cases

The game contains individual investigations with their own scenarios, information, clues, and conclusions.

- **The Last Signal** — Case 001
- **The Missing Prototype** — A separate investigation

Each case is designed around uncovering information, validating deductions, and working toward a resolution.

## 🛠️ Tech Stack

| Technology | Role |
|---|---|
| Python | Game logic and backend |
| Flask | Web application and routing |
| PostgreSQL | Persistent investigation data |
| SQL | Database operations and analytical queries |
| HTML | Application structure |
| CSS | Interface styling |
| JavaScript | Interactive gameplay and frontend behavior |

## 🏗️ Architecture

```text
Player
  │
  ▼
Web Interface
HTML · CSS · JavaScript
  │
  ▼
Flask Application
  │
  ├── Case & Session Logic
  ├── Interview System
  ├── Insight Validation
  ├── Clue Progression
  ├── Evidence Handling
  ├── Relationship Analysis
  ├── Timeline System
  └── Scoring & Accusation
  │
  ▼
PostgreSQL Database
  │
  ├── Cases
  ├── People
  ├── Evidence
  ├── Relationships
  ├── Timeline Events
  └── Investigation Progress
```

## 🗄️ Database Design

PostgreSQL serves as the persistent foundation of the game.

The project incorporates:

- Relational database design
- Primary and foreign keys
- Entity relationships
- Data integrity constraints
- SQL joins and multi-table queries
- Persistent game and investigation state
- Database migrations
- Structured evidence and timeline records

The database is not merely used to store game data—it supports the investigation mechanics and progression of the game.

## 🧪 Testing

CaseGraph includes tests for investigation progression, game-loop behavior, and advanced functionality.

```text
test_stage1_loop.py
test_full_game_loop.py
test_advanced_features.py
```

The full investigation loop has been tested, including clue progression, evidence persistence, scoring, accusation, and case completion.

## 🚀 Getting Started

### Prerequisites

- Python 3
- PostgreSQL
- Git

### Installation

Clone the repository:

```bash
git clone https://github.com/AkshatBansal06/CaseGraph.git
cd CaseGraph
```

Configure your PostgreSQL database and application connection settings.

Initialize the database using the provided schema and required migrations.

Install the dependencies required by the application.

### Launch

On Windows, launch the application using:

```text
Start CaseGraph.bat
```

Alternatively, start the Flask application using the appropriate Python configuration.

> Database setup and configuration are required before starting the game.

## 🎯 Project Objective

CaseGraph explores how database systems, backend logic, and interactive gameplay can work together to create an investigation-driven experience.

It combines detective gameplay with relational data modeling, persistent game state, clue progression, and interconnected investigative information.

---

## 👨‍💻 Developer

**Akshat Bansal**

B.Tech — Computer Science & Engineering

[GitHub Profile](https://github.com/AkshatBansal06)

## 🔗 Repository

[github.com/AkshatBansal06/CaseGraph](https://github.com/AkshatBansal06/CaseGraph)
