"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import sqlite3
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

current_dir = Path(__file__).parent
database_path = Path(os.getenv("MERGINGTON_DB_PATH", current_dir / "activities.sqlite"))

initial_activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def get_connection():
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK (max_participants > 0)
            );

            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_name TEXT NOT NULL REFERENCES activities(name)
                    ON DELETE CASCADE,
                email TEXT NOT NULL,
                UNIQUE(activity_name, email)
            );
            """
        )

        for name, activity in initial_activities.items():
            connection.execute(
                """
                INSERT OR IGNORE INTO activities
                    (name, description, schedule, max_participants)
                VALUES (?, ?, ?, ?)
                """,
                (name, activity["description"], activity["schedule"],
                 activity["max_participants"]),
            )
            for email in activity["participants"]:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO participants (activity_name, email)
                    VALUES (?, ?)
                    """,
                    (name, email),
                )


initialize_database()

# Mount the static files directory
app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")),
          name="static")


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    with get_connection() as connection:
        activity_rows = connection.execute(
            "SELECT name, description, schedule, max_participants "
            "FROM activities ORDER BY name"
        ).fetchall()
        participant_rows = connection.execute(
            "SELECT activity_name, email FROM participants ORDER BY id"
        ).fetchall()

    participants_by_activity = {row["name"]: [] for row in activity_rows}
    for row in participant_rows:
        participants_by_activity[row["activity_name"]].append(row["email"])

    return {
        row["name"]: {
            "description": row["description"],
            "schedule": row["schedule"],
            "max_participants": row["max_participants"],
            "participants": participants_by_activity[row["name"]],
        }
        for row in activity_rows
    }


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        activity = connection.execute(
            "SELECT max_participants FROM activities WHERE name = ?",
            (activity_name,),
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        participant_count = connection.execute(
            "SELECT COUNT(*) FROM participants WHERE activity_name = ?",
            (activity_name,),
        ).fetchone()[0]
        if participant_count >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="Activity is full")

        try:
            connection.execute(
                "INSERT INTO participants (activity_name, email) VALUES (?, ?)",
                (activity_name, email),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="Student is already signed up",
            )

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    with get_connection() as connection:
        activity_exists = connection.execute(
            "SELECT 1 FROM activities WHERE name = ?", (activity_name,)
        ).fetchone()
        if activity_exists is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        result = connection.execute(
            "DELETE FROM participants WHERE activity_name = ? AND email = ?",
            (activity_name, email),
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity",
            )

    return {"message": f"Unregistered {email} from {activity_name}"}
