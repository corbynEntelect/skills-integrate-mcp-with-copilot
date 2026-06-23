"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.

This application now includes a GraphQL BO API for centers, groups, students,
instructors, and dashboard analytics, with JWT-based authentication support.
"""

import jwt
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ariadne import (
    ObjectType,
    QueryType,
    MutationType,
    load_schema_from_path,
    make_executable_schema,
)
from ariadne.asgi import GraphQL
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(current_dir, "static")),
    name="static",
)

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60

roles = ["ADMIN", "USER"]

# In-memory activity database
activities: Dict[str, Dict[str, Any]] = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
}

# Business objects for BO GraphQL API
centers: List[Dict[str, Any]] = []
groups: List[Dict[str, Any]] = []
students: List[Dict[str, Any]] = []
instructors: List[Dict[str, Any]] = []
users: List[Dict[str, Any]] = []


def make_id() -> str:
    return str(uuid4())


def current_date_iso() -> str:
    return datetime.utcnow().isoformat()


def create_jwt_token(user: Dict[str, Any]) -> str:
    payload = {
        "sub": user["email"],
        "name": user["name"],
        "role": user.get("role", "USER"),
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ", 1)[1]
    payload = decode_jwt_token(token)
    if not payload:
        return None

    return next((user for user in users if user["email"] == payload.get("sub")), None)


def search_items(items: List[Dict[str, Any]], search_text: Optional[str], fields: List[str]) -> List[Dict[str, Any]]:
    if not search_text:
        return items

    lower_search = search_text.lower()
    result: List[Dict[str, Any]] = []
    for item in items:
        for field in fields:
            value = item.get(field)
            if value and lower_search in str(value).lower():
                result.append(item)
                break
    return result


def paginate_items(items: List[Dict[str, Any]], page: Optional[int], page_size: Optional[int]) -> List[Dict[str, Any]]:
    if not page or page < 1:
        page = 1
    if not page_size or page_size < 1:
        page_size = 20
    start = (page - 1) * page_size
    return items[start:start + page_size]


def require_auth(request: Request) -> None:
    if not get_current_user(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


# Minimal sample data for BO GraphQL API
centers.append({
    "id": make_id(),
    "name": "Mergington High Campus",
    "address": "12 School Lane",
    "city": "Mergington",
    "phone": "555-0101",
    "email": "frontdesk@mergington.edu",
    "type": "High School",
    "nature": "Schools",
    "notes": "Main extracurricular center",
    "active": True,
    "createdAt": current_date_iso(),
    "contacts": [
        {"name": "Alice Green", "email": "alice.green@mergington.edu", "phone": "555-0102", "sendInfo": True}
    ],
})

instructors.append({
    "id": make_id(),
    "name": "Ms. Carter",
    "corporateEmail": "carter@mergington.edu",
    "personalEmail": "carter.personal@gmail.com",
    "phone": "555-0103",
    "state": "Active",
    "training": "Physical Education",
    "areas": ["Sports", "Health"],
    "geographicalAvailability": ["Mergington"],
    "availability": [{"day": "Monday", "start": "14:00", "end": "17:00"}],
    "enrolled": True,
    "active": True,
    "notes": "Coach for gym classes",
    "groups": [],
})

students.append({
    "id": make_id(),
    "name": "Emma Lang",
    "email": "emma@mergington.edu",
    "birthDate": "2009-05-12",
    "enrolled": True,
    "active": True,
    "course": "10",
    "registrationDate": "2025-08-15",
    "notes": "Interested in sports and science",
    "contacts": [{"name": "Mrs. Lang", "email": "lang.family@mergington.edu", "phone": "555-0104", "sendInfo": True}],
    "groups": [],
})


def find_center(center_id: str) -> Optional[Dict[str, Any]]:
    return next((center for center in centers if center["id"] == center_id), None)


def find_group(group_id: str) -> Optional[Dict[str, Any]]:
    return next((group for group in groups if group["id"] == group_id), None)


def find_student(student_id: str) -> Optional[Dict[str, Any]]:
    return next((student for student in students if student["id"] == student_id), None)


def find_instructor(instructor_id: str) -> Optional[Dict[str, Any]]:
    return next((instructor for instructor in instructors if instructor["id"] == instructor_id), None)


type_defs = load_schema_from_path(current_dir / "schema.graphql")
query = QueryType()
mutation = MutationType()
center_type = ObjectType("Center")
group_type = ObjectType("Group")
student_type = ObjectType("Student")
instructor_type = ObjectType("Instructor")


@center_type.field("groups")
def resolve_center_groups(center_obj, info):
    return [group for group in groups if group["centerId"] == center_obj["id"]]


@group_type.field("center")
def resolve_group_center(group_obj, info):
    return find_center(group_obj["centerId"])


@group_type.field("students")
def resolve_group_students(group_obj, info):
    return [student for student in students if student["id"] in group_obj.get("studentIds", [])]


@group_type.field("instructors")
def resolve_group_instructors(group_obj, info):
    return [instructor for instructor in instructors if instructor["id"] in group_obj.get("instructorIds", [])]


@student_type.field("groups")
def resolve_student_groups(student_obj, info):
    return [group for group in groups if student_obj["id"] in group.get("studentIds", [])]


@instructor_type.field("groups")
def resolve_instructor_groups(instructor_obj, info):
    return [group for group in groups if instructor_obj["id"] in group.get("instructorIds", [])]


@query.field("getUser")
def resolve_get_user(_, info):
    return info.context.get("user")


@query.field("dashboard")
def resolve_dashboard(_, info):
    return {
        "userName": info.context.get("user", {}).get("name", "Guest"),
        "activeCenters": len([center for center in centers if center.get("active")]),
        "groups": len(groups),
        "activeInstructors": len([inst for inst in instructors if inst.get("enrolled")]),
        "activeStudents": len([student for student in students if student.get("enrolled")]),
    }


@query.field("getCenters")
def resolve_get_centers(_, info, searchText=None, orderBy=None, order=None, page=None, pageSize=None):
    filtered = search_items(centers, searchText, ["name", "address", "city", "email", "type", "nature", "notes"])
    if orderBy:
        filtered.sort(key=lambda item: str(item.get(orderBy, "")).lower(), reverse=(order == -1))
    return paginate_items(filtered, page, pageSize)


@query.field("getCenter")
def resolve_get_center(_, info, id):
    center = find_center(id)
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")
    return center


@query.field("getGroups")
def resolve_get_groups(_, info, searchText=None, orderBy=None, order=None, page=None, pageSize=None):
    filtered = search_items(groups, searchText, ["name", "type", "modality", "notes"])
    if orderBy:
        filtered.sort(key=lambda item: str(item.get(orderBy, "")).lower(), reverse=(order == -1))
    return paginate_items(filtered, page, pageSize)


@query.field("getGroup")
def resolve_get_group(_, info, id):
    group = find_group(id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@query.field("getStudents")
def resolve_get_students(_, info, searchText=None, orderBy=None, order=None, page=None, pageSize=None):
    filtered = search_items(students, searchText, ["name", "email", "course", "state", "notes"])
    if orderBy:
        filtered.sort(key=lambda item: str(item.get(orderBy, "")).lower(), reverse=(order == -1))
    return paginate_items(filtered, page, pageSize)


@query.field("getStudent")
def resolve_get_student(_, info, id):
    student = find_student(id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@query.field("getInstructors")
def resolve_get_instructors(_, info, searchText=None, orderBy=None, order=None, page=None, pageSize=None):
    filtered = search_items(instructors, searchText, ["name", "corporateEmail", "personalEmail", "areas", "notes"])
    if orderBy:
        filtered.sort(key=lambda item: str(item.get(orderBy, "")).lower(), reverse=(order == -1))
    return paginate_items(filtered, page, pageSize)


@query.field("getInstructor")
def resolve_get_instructor(_, info, id):
    instructor = find_instructor(id)
    if not instructor:
        raise HTTPException(status_code=404, detail="Instructor not found")
    return instructor


@mutation.field("loginWithGoogleToken")
def resolve_login_with_google(_, info, token):
    if not token.startswith("google:"):
        raise HTTPException(status_code=400, detail="Token must be a google token placeholder")
    _, email, name = token.split(":", 2) if ":" in token else (token, token, token)
    existing_user = next((user for user in users if user["email"] == email), None)
    if not existing_user:
        existing_user = {
            "id": make_id(),
            "name": name,
            "email": email,
            "picture": None,
            "role": "USER",
        }
        users.append(existing_user)
    return create_jwt_token(existing_user)


@mutation.field("createCenter")
def resolve_create_center(_, info, center):
    require_auth(info.context["request"])
    new_center = {
        "id": make_id(),
        "name": center["name"],
        "address": center.get("address", ""),
        "city": center.get("city", ""),
        "phone": center.get("phone", ""),
        "email": center.get("email", ""),
        "type": center.get("type", ""),
        "nature": center.get("nature", ""),
        "notes": center.get("notes", ""),
        "active": True,
        "createdAt": current_date_iso(),
        "contacts": center.get("contacts", []),
    }
    centers.append(new_center)
    return new_center


@mutation.field("createGroup")
def resolve_create_group(_, info, centerId, group):
    require_auth(info.context["request"])
    if not find_center(centerId):
        raise HTTPException(status_code=404, detail="Center not found")
    new_group = {
        "id": make_id(),
        "name": group["name"],
        "type": group.get("type", ""),
        "modality": group.get("modality", ""),
        "timetable": group.get("timetable", []),
        "centerId": centerId,
        "studentIds": group.get("studentIds", []),
        "instructorIds": group.get("instructorIds", []),
        "active": True,
        "createdAt": current_date_iso(),
    }
    groups.append(new_group)
    return new_group


@mutation.field("createStudent")
def resolve_create_student(_, info, student, groupIds=None):
    require_auth(info.context["request"])
    new_student = {
        "id": make_id(),
        "name": student["name"],
        "email": student["email"],
        "birthDate": student.get("birthDate"),
        "enrolled": True,
        "active": True,
        "course": student.get("course", ""),
        "notes": student.get("notes", ""),
        "contacts": student.get("contacts", []),
        "registrationDate": current_date_iso(),
        "groups": groupIds or [],
    }
    students.append(new_student)
    for group_id in groupIds or []:
        group = find_group(group_id)
        if group and new_student["id"] not in group.setdefault("studentIds", []):
            group["studentIds"].append(new_student["id"])
    return new_student


@mutation.field("createInstructor")
def resolve_create_instructor(_, info, instructor, groupIds=None):
    require_auth(info.context["request"])
    new_instructor = {
        "id": make_id(),
        "name": instructor["name"],
        "corporateEmail": instructor.get("corporateEmail"),
        "personalEmail": instructor.get("personalEmail"),
        "phone": instructor.get("phone"),
        "state": instructor.get("state", "Active"),
        "training": instructor.get("training", ""),
        "areas": instructor.get("areas", []),
        "geographicalAvailability": instructor.get("geographicalAvailability", []),
        "availability": instructor.get("availability", []),
        "enrolled": True,
        "active": True,
        "notes": instructor.get("notes", ""),
        "groups": groupIds or [],
    }
    instructors.append(new_instructor)
    for group_id in groupIds or []:
        group = find_group(group_id)
        if group and new_instructor["id"] not in group.setdefault("instructorIds", []):
            group["instructorIds"].append(new_instructor["id"])
    return new_instructor


class AuthDirective:
    def visit_field_definition(self, field, object_type):
        def default_resolver(obj, info, **kwargs):
            return None

        original_resolver = field.resolve or default_resolver

        def resolve_auth(obj, info, **kwargs):
            if not info.context.get("user"):
                raise Exception("Unauthorized")
            return original_resolver(obj, info, **kwargs)

        field.resolve = resolve_auth
        return field


schema = make_executable_schema(
    type_defs,
    query,
    mutation,
    center_type,
    group_type,
    student_type,
    instructor_type,
)

try:
    from graphql.utilities import SchemaDirectiveVisitor

    SchemaDirectiveVisitor.visit_schema_directives(schema, {"auth": AuthDirective})
except Exception:
    pass


graphql_app = GraphQL(
    schema,
    debug=True,
    context_value=lambda request: {
        "request": request,
        "user": get_current_user(request),
    },
)

app.mount("/graphql", graphql_app)


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity = activities[activity_name]
    if email in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student is already signed up")

    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity = activities[activity_name]
    if email not in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
