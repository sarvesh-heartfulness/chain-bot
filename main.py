from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
import uvicorn
import json
import os
import uuid
import re
from datetime import datetime
from typing import Dict, List, Optional


class TravelRequirements(BaseModel):
    transport_mode: str
    arrival_location: str


class AccommodationDetails(BaseModel):
    type: str
    number_of_people: int


class RegistrationStep(BaseModel):
    conversation_id: str
    current_step: str
    user_input: Optional[str] = None


class RegistrationData(BaseModel):
    full_name: str
    email: EmailStr
    mobile: str
    age_group: str = Field(..., pattern="^(18-25|26-40|41-60|61+)$")
    abhyasi_id: str
    arrival_date: str
    departure_date: str
    travel_requirements: Optional[TravelRequirements] = None
    accommodation: Optional[AccommodationDetails] = None


class ConversationManager:
    def __init__(self, conversations_file: str = "conversations.json"):
        self.conversations_file = conversations_file
        self.conversations = self._load_conversations()

    def _load_conversations(self) -> List[Dict]:
        if not os.path.exists(self.conversations_file):
            return []

        try:
            with open(self.conversations_file, "r") as file:
                return json.load(file)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_conversations(self):
        try:
            with open(self.conversations_file, "w") as file:
                json.dump(self.conversations, file, indent=2)
        except IOError:
            print("Error saving conversations.")

    def validate_email(self, email: str) -> bool:
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(email_regex, email) is not None

    def validate_phone(self, phone: str) -> bool:
        phone_regex = r"^\+?1?\d{10,14}$"
        return re.match(phone_regex, phone) is not None

    def validate_date(self, date_str: str) -> bool:
        try:
            datetime.strptime(date_str, "%d-%m-%Y")
            return True
        except ValueError:
            return False

    def start_conversation(self) -> str:
        conversation_id = str(uuid.uuid4())
        conversation = {
            "id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "steps": [],
            "current_step": "start",
            "registration_data": {},
        }
        self.conversations.append(conversation)
        self._save_conversations()
        return conversation_id

    def process_step(self, conversation_id: str, step: RegistrationStep) -> Dict:
        conversation = next(
            (conv for conv in self.conversations if conv["id"]
             == conversation_id), None
        )
        if not conversation:
            raise HTTPException(
                status_code=404, detail="Conversation not found")

        if conversation["current_step"] == "start":
            conversation["current_step"] = "name"
            return {"next_step": "name", "next_step_message": "Enter your full name"}

        elif conversation["current_step"] == "name":
            if not step.user_input or len(step.user_input) < 2:
                return {
                    "error": "Please enter a valid name (at least 2 characters)",
                    "error_step": "name",
                }
            conversation["registration_data"]["full_name"] = step.user_input
            conversation["current_step"] = "email"
            return {
                "next_step": "email",
                "next_step_message": "Enter your email address",
            }

        elif conversation["current_step"] == "email":
            if not self.validate_email(step.user_input):
                return {
                    "error": "Please enter a valid email address",
                    "error_step": "email",
                }
            conversation["registration_data"]["email"] = step.user_input
            conversation["current_step"] = "mobile"
            return {
                "next_step": "mobile",
                "next_step_message": "Enter your mobile number",
            }

        elif conversation["current_step"] == "mobile":
            if not self.validate_phone(step.user_input):
                return {
                    "error": "Please enter a valid mobile number",
                    "error_step": "mobile",
                }
            conversation["registration_data"]["mobile"] = step.user_input
            conversation["current_step"] = "age_group"
            return {
                "next_step": "age_group",
                "next_step_message": "Select your age group",
                "options": ["18-25", "26-40", "41-60", "61+"],
            }

        elif conversation["current_step"] == "age_group":
            age_groups = ["18-25", "26-40", "41-60", "61+"]
            if step.user_input not in age_groups:
                return {
                    "error": "Invalid age group selection",
                    "error_step": "age_group",
                }
            conversation["registration_data"]["age_group"] = step.user_input
            conversation["current_step"] = "abhyasi_id"
            return {
                "next_step": "abhyasi_id",
                "next_step_message": "Enter your Abhyasi ID",
            }

        elif conversation["current_step"] == "abhyasi_id":
            if not step.user_input or len(step.user_input) < 4:
                return {
                    "error": "Please enter a valid Abhyasi ID",
                    "error_step": "abhyasi_id",
                }
            conversation["registration_data"]["abhyasi_id"] = step.user_input
            conversation["current_step"] = "arrival_date"
            return {
                "next_step": "arrival_date",
                "next_step_message": "Enter your arrival date (DD-MM-YYYY)",
            }

        elif conversation["current_step"] == "arrival_date":
            if not self.validate_date(step.user_input):
                return {
                    "error": "Please enter a valid date (DD-MM-YYYY format)",
                    "error_step": "arrival_date",
                }
            conversation["registration_data"]["arrival_date"] = step.user_input
            conversation["current_step"] = "departure_date"
            return {
                "next_step": "departure_date",
                "next_step_message": "Enter your departure date (DD-MM-YYYY)",
            }

        elif conversation["current_step"] == "departure_date":
            if not self.validate_date(step.user_input):
                return {
                    "error": "Please enter a valid date (DD-MM-YYYY format)",
                    "error_step": "departure_date",
                }
            conversation["registration_data"]["departure_date"] = step.user_input
            conversation["current_step"] = "travel_requirements_confirmation"
            return {
                "next_step": "travel_requirements_confirmation",
                "next_step_message": "Do you have any travel requirements? (yes/no)",
            }

        elif conversation["current_step"] == "travel_requirements_confirmation":
            if step.user_input.lower() in ["yes", "y"]:
                conversation["current_step"] = "travel_requirements_mode"
                return {
                    "next_step": "travel_requirements_mode",
                    "next_step_message": "Select transport mode",
                    "options": ["Air", "Train", "Bus", "Car"]
                }
            elif step.user_input.lower() in ["no", "n"]:
                conversation["current_step"] = "accommodation_confirmation"
                return {
                    "next_step": "accommodation_confirmation",
                    "next_step_message": "Do you need accommodation? (yes/no)",
                }
            else:
                return {
                    "error": "Please answer yes or no",
                    "error_step": "travel_requirements_confirmation",
                }

        elif conversation["current_step"] == "travel_requirements_mode":
            transport_modes = ["air", "train", "bus", "car"]
            if step.user_input.lower() not in transport_modes:
                return {
                    "error": "Invalid transport mode",
                    "error_step": "travel_requirements_mode",
                    "options": transport_modes
                }

            conversation["temp_travel_requirements"] = {
                "transport_mode": step.user_input.lower()}
            conversation["current_step"] = "travel_requirements_location"
            return {
                "next_step": "travel_requirements_location",
                "next_step_message": "Enter your arrival location",
            }

        elif conversation["current_step"] == "travel_requirements_location":
            if not step.user_input:
                return {
                    "error": "Please provide arrival location",
                    "error_step": "travel_requirements_location",
                }

            conversation["temp_travel_requirements"]["arrival_location"] = step.user_input
            conversation["registration_data"]["travel_requirements"] = conversation["temp_travel_requirements"]
            del conversation["temp_travel_requirements"]

            conversation["current_step"] = "accommodation_confirmation"
            return {
                "next_step": "accommodation_confirmation",
                "next_step_message": "Do you need accommodation? (yes/no)",
            }

        elif conversation["current_step"] == "accommodation_confirmation":
            if step.user_input.lower() in ["yes", "y"]:
                conversation["current_step"] = "accommodation_type"
                return {
                    "next_step": "accommodation_type",
                    "next_step_message": "Select accommodation type",
                    "options": ["Dormitory", "Guest House", "Single Room", "Shared Room"]
                }
            elif step.user_input.lower() in ["no", "n"]:
                conversation["current_step"] = "confirmation"
                return {
                    "next_step": "confirmation",
                    "next_step_message": "Confirm your registration details",
                    "registration_data": conversation["registration_data"],
                }
            else:
                return {
                    "error": "Please answer yes or no",
                    "error_step": "accommodation_confirmation",
                }

        elif conversation["current_step"] == "accommodation_type":
            accommodation_types = ["Dormitory",
                                   "Guest House", "Single Room", "Shared Room"]
            if step.user_input not in accommodation_types:
                return {
                    "error": "Invalid accommodation type",
                    "error_step": "accommodation_type",
                    "options": accommodation_types
                }

            conversation["temp_accommodation"] = {"type": step.user_input}
            conversation["current_step"] = "accommodation_people"
            return {
                "next_step": "accommodation_people",
                "next_step_message": "Enter number of people for accommodation",
            }

        elif conversation["current_step"] == "accommodation_people":
            try:
                people_count = int(step.user_input)
                if people_count < 1 or people_count > 10:
                    raise ValueError
            except ValueError:
                return {
                    "error": "Please enter a valid number of people (1-10)",
                    "error_step": "accommodation_people",
                }

            conversation["temp_accommodation"]["number_of_people"] = people_count
            conversation["registration_data"]["accommodation"] = conversation["temp_accommodation"]
            del conversation["temp_accommodation"]

            conversation["current_step"] = "confirmation"
            return {
                "next_step": "confirmation",
                "next_step_message": "Confirm your registration details",
                "registration_data": conversation["registration_data"],
            }

        elif conversation["current_step"] == "confirmation":
            if step.user_input.lower() in ["yes", "y"]:
                conversation["registration_data"]["registration_timestamp"] = datetime.now(
                ).isoformat()
                conversation["current_step"] = "completed"
                self._save_conversations()
                return {
                    "next_step": "completed",
                    "next_step_message": "Registration completed successfully!",
                    "conversation_id": conversation_id,
                }
            else:
                conversation["current_step"] = "cancelled"
                return {
                    "next_step": "cancelled",
                    "next_step_message": "Registration cancelled",
                }

        self._save_conversations()
        raise HTTPException(
            status_code=400, detail="Invalid conversation state")


# Initialize FastAPI
app = FastAPI(title="Bhandara Event Registration API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global conversation manager
conversation_manager = ConversationManager()


@app.post("/start")
def start_conversation():
    """
    Initiate a new registration conversation.
    """
    conversation_id = conversation_manager.start_conversation()
    return {"conversation_id": conversation_id}


@app.post("/process")
def process_registration_step(step: RegistrationStep):
    """
    Process a single step in the registration workflow.
    """
    return conversation_manager.process_step(step.conversation_id, step)


@app.get("/registrations")
def list_registrations(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "timestamp",
    sort_order: str = "desc",
):
    """
    Retrieve a list of completed registrations.
    """
    # Filter only completed registrations
    completed_registrations = [
        conv["registration_data"]
        for conv in conversation_manager.conversations
        if conv.get("current_step") == "completed"
    ]

    # Sort registrations
    if sort_by == "timestamp":
        completed_registrations.sort(
            key=lambda x: x.get("registration_timestamp", ""),
            reverse=(sort_order == "desc"),
        )

    # Pagination
    total_count = len(completed_registrations)
    paginated_registrations = completed_registrations[skip: skip + limit]

    return {
        "registrations": paginated_registrations,
        "total_count": total_count,
        "skip": skip,
        "limit": limit,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
