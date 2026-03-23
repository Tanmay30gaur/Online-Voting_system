from flask import Flask, render_template, request, redirect, session, flash
from db import get_db_connection
import mysql.connector
import re

app = Flask(__name__)
app.secret_key = "securekey123"


# ================= HOME =================
@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")


# ================= CHOOSE ELECTION =================
@app.route("/choose-election")
def choose_election():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT state_status, national_status,
               state_start, state_end,
               national_start, national_end
        FROM election_control WHERE id=1
    """)

    data = cursor.fetchone()
    conn.close()

    return render_template(
        "choose_election.html",
        state_status=data[0],
        national_status=data[1],
        state_start=data[2],
        state_end=data[3],
        national_start=data[4],
        national_end=data[5]
    )


# ================= CAST VOTE =================
@app.route("/cast-vote", methods=["GET", "POST"])
def vote():
    election_type = request.args.get("type")

    conn = get_db_connection()
    cursor = conn.cursor()

    # CHECK STATUS
    cursor.execute("SELECT state_status, national_status FROM election_control WHERE id=1")
    status = cursor.fetchone()

    if request.method == "POST":

        user_id = request.form["user_id"]
        age = int(request.form["age"])
        voter_id = request.form["voter_id"].strip().upper()
        party = request.form["party"]

        # CHECK CLOSED (no redirect ❌)
        if election_type == "state" and not status[0]:
            flash("❌ State Election is CLOSED", "danger")
            return render_template("user_vote.html")

        if election_type == "national" and not status[1]:
            flash("❌ National Election is CLOSED", "danger")
            return render_template("user_vote.html")

        # AGE VALIDATION
        if age < 18 or age > 120:
            flash("❌ Invalid age", "danger")
            return render_template("user_vote.html")

        # VOTER ID VALIDATION
        if not re.match(r'^[A-Z]{3}[0-9]{7}$', voter_id):
            flash("❌ Invalid Voter ID format (ABC1234567)", "danger")
            return render_template("user_vote.html")

        # USER CHECK
        cursor.execute("SELECT 1 FROM Voting WHERE User_Id=%s", (user_id,))
        if cursor.fetchone():
            flash("⚠️ User already voted", "warning")
            return render_template("user_vote.html")

        # VOTER ID CHECK
        cursor.execute("SELECT 1 FROM Voting WHERE Voter_ID=%s", (voter_id,))
        if cursor.fetchone():
            flash("⚠️ This Voter ID has already voted", "warning")
            return render_template("user_vote.html")

        try:
            cursor.execute(
                "INSERT INTO Voting (User_Id, Age, Voter_ID, Party, Election_Type) VALUES (%s,%s,%s,%s,%s)",
                (user_id, age, voter_id, party, election_type)
            )

            conn.commit()
            conn.close()

            return render_template("thank_you.html")

        except mysql.connector.IntegrityError:
            flash("❌ Duplicate entry detected!", "danger")
            return render_template("user_vote.html")

    return render_template("user_vote.html")


# ================= ADMIN LOGIN =================
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        admin = request.form["admin"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM authenticator WHERE adm=%s AND pswd=%s",
            (admin, password)
        )

        if cursor.fetchone():
            session["admin"] = True
            conn.close()
            return redirect("/admin-panel")

        conn.close()
        flash("❌ Invalid credentials", "danger")

    return render_template("admin_login.html")


# ================= TOGGLE =================
@app.route("/toggle-election/<type>")
def toggle_election(type):
    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()

    if type == "state":
        cursor.execute("UPDATE election_control SET state_status = NOT state_status WHERE id=1")

    elif type == "national":
        cursor.execute("UPDATE election_control SET national_status = NOT national_status WHERE id=1")

    conn.commit()
    conn.close()

    return redirect("/admin-panel")


# ================= UPDATE DATES =================
@app.route("/update-dates", methods=["POST"])
def update_dates():
    if "admin" not in session:
        return redirect("/admin-login")

    state_start = request.form["state_start"]
    state_end = request.form["state_end"]
    national_start = request.form["national_start"]
    national_end = request.form["national_end"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE election_control 
        SET state_start=%s, state_end=%s,
            national_start=%s, national_end=%s
        WHERE id=1
    """, (state_start, state_end, national_start, national_end))

    conn.commit()
    conn.close()

    return redirect("/admin-panel")


# ================= ADMIN PANEL =================
@app.route("/admin-panel")
def admin_panel():
    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM Voting")
    total_votes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Voting WHERE Election_Type='state'")
    state_votes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Voting WHERE Election_Type='national'")
    national_votes = cursor.fetchone()[0]

    cursor.execute("""
        SELECT state_status, national_status,
               state_start, state_end,
               national_start, national_end
        FROM election_control WHERE id=1
    """)

    data = cursor.fetchone()
    conn.close()

    return render_template(
        "admin_panel.html",
        total_votes=total_votes,
        state_votes=state_votes,
        national_votes=national_votes,
        state_status=data[0],
        national_status=data[1],
        state_start=data[2],
        state_end=data[3],
        national_start=data[4],
        national_end=data[5]
    )


# ================= RESULTS =================
@app.route("/results/<etype>")
def results(etype):
    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT Party, COUNT(*) FROM Voting WHERE Election_Type=%s GROUP BY Party",
        (etype,)
    )
    data = cursor.fetchall()

    labels = [row[0] for row in data]
    votes = [row[1] for row in data]

    cursor.execute(
        "SELECT COUNT(*) FROM Voting WHERE Election_Type=%s",
        (etype,)
    )
    total = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "results.html",
        labels=labels,
        votes=votes,
        total=total,
        etype=etype
    )


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/home")


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)