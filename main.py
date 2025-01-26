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


class RegistrationStep(BaseModel):
    conversation_id: str
    current_step: str
    user_input: Optional[str] = None


class RegistrationData(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    age_group: Optional[str] = Field(None, pattern="^(18-25|26-40|41-60|61+)$")
    meditation_experience: Optional[str] = Field(
        None, pattern="^(Beginner|Intermediate|Advanced)$"
    )


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
            (conv for conv in self.conversations if conv["id"] == conversation_id), None
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

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
            conversation["current_step"] = "phone"
            return {
                "next_step": "phone",
                "next_step_message": "Enter your phone number",
            }

        elif conversation["current_step"] == "phone":
            if not self.validate_phone(step.user_input):
                return {
                    "error": "Please enter a valid phone number",
                    "error_step": "phone",
                }
            conversation["registration_data"]["phone"] = step.user_input
            conversation["current_step"] = "age_group"
            return {
                "next_step": "age_group",
                "next_step_message": "Select your age group",
                "options": [
                    {"value": "18-25", "label": "18-25"},
                    {"value": "26-40", "label": "26-40"},
                    {"value": "41-60", "label": "41-60"},
                    {"value": "61+", "label": "61+"},
                ],
            }

        elif conversation["current_step"] == "age_group":
            age_groups = ["18-25", "26-40", "41-60", "61+"]
            if step.user_input not in age_groups:
                return {
                    "error": "Invalid age group selection",
                    "error_step": "age_group",
                }
            conversation["registration_data"]["age_group"] = step.user_input
            conversation["current_step"] = "meditation_experience"
            return {
                "next_step": "meditation_experience",
                "next_step_message": "Select your meditation experience",
                "options": [
                    {"value": "Beginner", "label": "Beginner"},
                    {"value": "Intermediate", "label": "Intermediate"},
                    {"value": "Advanced", "label": "Advanced"},
                ],
            }

        elif conversation["current_step"] == "meditation_experience":
            exp_levels = ["Beginner", "Intermediate", "Advanced"]
            if step.user_input not in exp_levels:
                return {
                    "error": "Invalid meditation experience selection",
                    "error_step": "meditation_experience",
                }
            conversation["registration_data"]["meditation_experience"] = step.user_input
            conversation["current_step"] = "confirmation"
            return {
                "next_step": "confirmation",
                "next_step_message": "Confirm your registration details",
                "registration_data": conversation["registration_data"],
            }

        elif conversation["current_step"] == "confirmation":
            if step.user_input.lower() in ["yes", "y"]:
                conversation["registration_data"]["registration_timestamp"] = (
                    datetime.now().isoformat()
                )
                conversation["current_step"] = "completed"
                self._save_conversations()
                return {
                    "next_step": "completed",
                    "next_step_message": "Registration completed successfully!",
                    "message": "Registration completed",
                    "conversation_id": conversation_id,
                }
            else:
                conversation["current_step"] = "cancelled"
                return {
                    "next_step": "cancelled",
                    "next_step_message": "Registration cancelled",
                    "message": "Registration cancelled",
                }

        self._save_conversations()
        raise HTTPException(status_code=400, detail="Invalid conversation state")


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

    Returns:
    ---
        dict: A dictionary containing a unique conversation ID for tracking
              the registration process.

    Example:
        {
            "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
        }
    """
    conversation_id = conversation_manager.start_conversation()
    return {"conversation_id": conversation_id}


@app.post("/process")
def process_registration_step(step: RegistrationStep):
    """
    Process a single step in the registration workflow.

    Args:
    ---
        step (RegistrationStep): Contains conversation details and user input.
            - conversation_id (str): Unique identifier for the current conversation
            - current_step (str): Current stage in registration process
            - user_input (str, optional): User's response at current step

    Returns:
    ---
        dict: Response containing:
            - next_step (str): Identifier for the next registration step
            - next_step_message (str): Instruction or prompt for the next step
            - options (list, optional): Selectable options for certain steps
            - registration_data (dict, optional): Collected registration information
            - error (str, optional): Validation error message
            - error_step (str, optional): Step where validation failed

    Raises:
    ---
        HTTPException: If conversation is not found or in an invalid state
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

    Args:
    ---
        skip (int, optional): Number of registrations to skip for pagination. Defaults to 0.
        limit (int, optional): Maximum number of registrations to return. Defaults to 100.
        sort_by (str, optional): Field to sort registrations by. Defaults to "timestamp".
        sort_order (str, optional): Sort order - "asc" or "desc". Defaults to "desc".

    Returns:
    ---
        dict: A list of completed registrations with total count
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
    paginated_registrations = completed_registrations[skip : skip + limit]

    return {
        "registrations": paginated_registrations,
        "total_count": total_count,
        "skip": skip,
        "limit": limit,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
