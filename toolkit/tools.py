import pandas as pd
from langchain_core.tools import tool
from data_models.models import *
from core.config import DoctorName, Specialization
from langchain_core.runnables import RunnableConfig
from db.database import SessionLocal 
from db.models import Patient
from utils.notification import send_email
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "doctor_availability.csv")

def convert_to_am_pm(time):
    """Convert time from 24-hour format to 12-hour AM/PM format."""
    hour, minute = map(int, time.split(':'))
    period = 'AM' if hour < 12 else 'PM'
    hour = hour % 12
    hour = 12 if hour == 0 else hour
    return f"{hour}:{minute:02d} {period}"

def get_patient_details(patient_id: int) -> str:
    db = SessionLocal()
    try:
        patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
        if patient:
            return patient.email, patient.fullname
        return None
    except Exception:
        return None
    finally:
        db.close()

@tool
def check_availability_by_doctor(doctor_name: DoctorName, desired_date: DateModel):
    """
    Check availability for a given doctor on a specific validated date.
    
    Args:
        doctor_name (DoctorName): Name of the doctor (restricted set).
        desired_date (DateModel): Validated date string in format DD-MM-YYYY.
    
    Returns:
        A message with a list if available time slots for the doctor on the selected date or a message indicating no availability.
    """
    try:
        df= pd.read_csv(CSV_PATH )
        available_slots = df[
            (df['doctor_name'].str.lower() == doctor_name.lower()) & 
            (df['date_slot'].str.startswith(desired_date.date)) &
            (df['is_available'] == True)
            ]['date_slot'].apply(lambda dt: dt.split(' ')[-1]).tolist()
        
        if len(available_slots) == 0:
            return f"No available slots for Dr. {doctor_name} on {desired_date.date} in the entire day."
        else:
            slots_str = ', '.join(available_slots)
            return f"Available slots for Dr. {doctor_name} on {desired_date.date} are: {slots_str}."
    except FileNotFoundError:
        return "Error: The availability data file was not found."
    except KeyError as e:
        return f"Error: Missing expected column {e} in the dataset."
    except Exception as e:
        return f"Unexpected error: {str(e)}"
            
@tool
def check_availability_by_specialization(specialization: Specialization, desired_date: DateModel):
    """
    Check availability for doctors of a given specialization on a specific validated date.
    
    Args:
        specialization (Specialization): Specialization of the doctor (restricted set).
        desired_date (DateModel): Validated date string in format DD-MM-YYYY.
    
    Returns:
        A message with a list if available time slots for doctors of the given specialization on the selected date or a message indicating no availability.
    """
    try:
        df= pd.read_csv(CSV_PATH )
        available_slots = df[
            (df['specialization'].str.lower() == specialization.lower()) & 
            (df['date_slot'].str.startswith(desired_date.date)) &
            (df['is_available'] == True)
            ][['doctor_name','date_slot']]
        
        if available_slots.empty:
            return f"No available slots for {specialization.replace('_', ' ')} on {desired_date.date} in the entire day."
        else:
            result_lines = []
            for _, row in available_slots.iterrows():
                time_slot = convert_to_am_pm(row['date_slot'].split(' ')[-1])
                result_lines.append(f"Dr. {row['doctor_name']} at {time_slot}")
            result_str = '\n'.join(result_lines)
            return f"Available slots for {specialization.replace('_', ' ')} on {desired_date.date} are:\n{result_str}."
    except FileNotFoundError:
        return "Error: The availability data file was not found."
    except KeyError as e:
        return f"Error: Missing expected column {e} in the dataset."
    except Exception as e:
        return f"Unexpected error: {str(e)}"

@tool
def book_appointment(doctor_name: DoctorName, appointment_datetime: DateTimeModel, config: RunnableConfig):
    """
    Book an appointment with a specific doctor at a given validated date and time for a patient.
    
    Args:
        doctor_name (DoctorName): Name of the doctor (restricted set).
        appointment_datetime (DateTimeModel): Validated date-time string in format DD-MM-YYYY HH:MM.
    
    Returns:
        A confirmation message if the appointment is successfully booked or a message indicating unavailability.
    """
    try:
        patient_id=config["configurable"].get("thread_id")
        df= pd.read_csv(CSV_PATH )
        slot_str = f"{appointment_datetime.datetime}"
        is_available = not df[
            (df['doctor_name'].str.lower() == doctor_name.lower()) & 
            (df['date_slot'] == slot_str) &
            (df['is_available'] == True)
            ].empty
        
        if is_available:
            df.loc[
                (df['doctor_name'].str.lower() == doctor_name.lower()) & 
                (df['date_slot'] == slot_str), ['is_available','patient_to_attend']
            ] = [False,patient_id]

            df.to_csv(CSV_PATH, index=False)
            email, fullName = get_patient_details(patient_id)
            if email and fullName:
                subject = "Appointment Confirmation"
                body = f"Dear {fullName},\n\nYour appointment with Dr. {doctor_name} has been successfully booked on {appointment_datetime.datetime}.\n\nThank you!"
                send_email(email, subject, body)

            return f"Appointment successfully booked with Dr. {doctor_name} on {appointment_datetime.datetime} for patient ID {patient_id}."
        else:
            return f"Sorry, Dr. {doctor_name} is not available on {appointment_datetime.datetime}. Please choose a different time."
    except FileNotFoundError:
        return "Error: The availability data file was not found."
    except KeyError as e:
        return f"Error: Missing expected column {e} in the dataset."
    except Exception as e:
        return f"Unexpected error: {str(e)}"

@tool
def cancel_appointment(doctor_name: DoctorName, appointment_datetime: DateTimeModel, config: RunnableConfig):
    """
    Cancel an existing appointment with a specific doctor at a given validated date and time for a patient.
    
    Args:
        doctor_name (DoctorName): Name of the doctor (restricted set).
        appointment_datetime (DateTimeModel): Validated date-time string in format DD-MM-YYYY HH:MM.
    
    Returns:
        A confirmation message if the appointment is successfully canceled or a message indicating no such appointment exists.
    """
    try:
        patient_id=config["configurable"].get("thread_id")
        df= pd.read_csv(CSV_PATH )
        slot_str = f"{appointment_datetime.datetime}"
        appointment_exists = not df[
            (df['doctor_name'].str.lower() == doctor_name.lower()) & 
            (df['date_slot'] == slot_str) &
            (df['patient_to_attend'] == patient_id) &
            (df['is_available'] == False)
            ].empty
        
        if appointment_exists:
            df.loc[
                (df['doctor_name'].str.lower() == doctor_name.lower()) & 
                (df['date_slot'] == slot_str) &
                (df['patient_to_attend'] == patient_id), ['is_available','patient_to_attend']
            ] = [True, None]

            df.to_csv(CSV_PATH, index=False)
            email, fullName = get_patient_details(patient_id)
            if email and fullName:
                subject = "Appointment Cancellation"
                body = f"Dear {fullName},\n\nYour appointment with Dr. {doctor_name} on {appointment_datetime.datetime} has been successfully canceled.\n\nThank you!"
                send_email(email, subject, body)
            return f"Appointment with Dr. {doctor_name} on {appointment_datetime.datetime} for patient ID {patient_id} has been successfully canceled."
        else:
            return f"No existing appointment found with Dr. {doctor_name} on {appointment_datetime.datetime} for patient ID {patient_id}."
    except FileNotFoundError:
        return "Error: The availability data file was not found."
    except KeyError as e:
        return f"Error: Missing expected column {e} in the dataset."
    except Exception as e:
        return f"Unexpected error: {str(e)}"
    
@tool
def reschedule_appointment(doctor_name: DoctorName, old_appointment_datetime: DateTimeModel, new_appointment_datetime: DateTimeModel,config: RunnableConfig):
    """
    Reschedule an existing appointment with a specific doctor from an old date and time to a new date and time for a patient.
    
    Args:
        doctor_name (DoctorName): Name of the doctor (restricted set).
        old_appointment_datetime (DateTimeModel): Validated old date-time string in format DD-MM-YYYY HH:MM.
        new_appointment_datetime (DateTimeModel): Validated new date-time string in format DD-MM-YYYY HH:MM.
    
    Returns:
        A confirmation message if the appointment is successfully rescheduled or a message indicating failure due to unavailability or no existing appointment.
    """
    try:
        patient_id=config["configurable"].get("thread_id")
        df= pd.read_csv(CSV_PATH )
        old_slot_str = f"{old_appointment_datetime.datetime}"
        new_slot_str = f"{new_appointment_datetime.datetime}"
        
        appointment_exists = not df[
            (df['doctor_name'].str.lower() == doctor_name.lower()) & 
            (df['date_slot'] == old_slot_str) &
            (df['patient_to_attend'] == patient_id) &
            (df['is_available'] == False)
            ].empty
        
        new_slot_available = not df[
            (df['doctor_name'].str.lower() == doctor_name.lower()) & 
            (df['date_slot'] == new_slot_str) &
            (df['is_available'] == True)
            ].empty
        
        if appointment_exists and new_slot_available:
            # Cancel old appointment
            df.loc[
                (df['doctor_name'].str.lower() == doctor_name.lower()) & 
                (df['date_slot'] == old_slot_str) &
                (df['patient_to_attend'] == patient_id), ['is_available','patient_to_attend']
            ] = [True, None]
            
            # Book new appointment
            df.loc[
                (df['doctor_name'].str.lower() == doctor_name.lower()) & 
                (df['date_slot'] == new_slot_str), ['is_available','patient_to_attend']
            ] = [False, patient_id]

            df.to_csv(CSV_PATH, index=False)
            email, fullName = get_patient_details(patient_id)
            if email and fullName:
                subject = "Appointment Rescheduling"
                body = f"Dear {fullName},\n\nYour appointment with Dr. {doctor_name} has been successfully rescheduled from {old_appointment_datetime.datetime} to {new_appointment_datetime.datetime}.\n\nThank you!"
                send_email(email, subject, body)
            return f"Appointment with Dr. {doctor_name} has been successfully rescheduled from {old_appointment_datetime.datetime} to {new_appointment_datetime.datetime} for patient ID {patient_id}."
        elif not appointment_exists:
            return f"No existing appointment found with Dr. {doctor_name} on {old_appointment_datetime.datetime} for patient ID {patient_id}."
        else:
            return f"Sorry, Dr. {doctor_name} is not available on {new_appointment_datetime.datetime}. Please choose a different time."
    except FileNotFoundError:
        return "Error: The availability data file was not found."
    except KeyError as e:
        return f"Error: Missing expected column {e} in the dataset."
    except Exception as e:
        return f"Unexpected error: {str(e)}"
    
@tool
def get_available_doctors_on_date(desired_date: DateModel):
    """
    Get a list of all doctors along with their specializations who have at least one available time slot on a specific validated date.
    
    Args:
        desired_date (DateModel): Validated date string in format DD-MM-YYYY.
    
    Returns:
        A message with a list of available doctors along with their specializations on the specified date or a message indicating no doctors are available.
    """
    try:
        df= pd.read_csv(CSV_PATH )
        available_doctors = df[
            (df['date_slot'].str.startswith(desired_date.date)) &
            (df['is_available'] == True)
            ][['doctor_name','specialization']].drop_duplicates()
        
        if available_doctors.empty:
            return f"No doctors are available on {desired_date.date}."
        else:
            result_lines = []
            for _, row in available_doctors.iterrows():
                spec_formatted = row['specialization'].replace('_', ' ')
                result_lines.append(f"Dr. {row['doctor_name']} ({spec_formatted})")
            result_str = ', '.join(result_lines)
            return f"The following doctors are available on {desired_date.date}: {result_str}."
    except FileNotFoundError:
        return "Error: The availability data file was not found."
    except KeyError as e:
        return f"Error: Missing expected column {e} in the dataset."
    except Exception as e:
        return f"Unexpected error: {str(e)}"
    
@tool
def get_available_doctors():
    """
    Get a list of all doctors who have at least one available time slot.
    
    Returns:
        A message with a list of available doctors or a message indicating no doctors are available.
    """
    try:
        df= pd.read_csv(CSV_PATH )
        available_doctors = df[df['is_available'] == True]['doctor_name'].unique().tolist()
        
        if len(available_doctors) == 0:
            return "No doctors are currently available."
        else:
            doctors_str = ', '.join(available_doctors)
            return f"The following doctors have available slots: {doctors_str}."
    except FileNotFoundError:
        return "Error: The availability data file was not found."
    except KeyError as e:
        return f"Error: Missing expected column {e} in the dataset."
    except Exception as e:
        return f"Unexpected error: {str(e)}"
    
@tool
def get_available_specializations():
    """
    Get a list of all specializations that have at least one available time slot.
    
    Returns:
        A message with a list of available specializations or a message indicating no specializations are available.
    """
    try:
        df= pd.read_csv(CSV_PATH )
        available_specializations = df[df['is_available'] == True]['specialization'].unique().tolist()
        
        if len(available_specializations) == 0:
            return "No specializations are currently available."
        else:
            specs_str = ', '.join(available_specializations)
            return f"The following specializations have available slots: {specs_str}."
    except FileNotFoundError:
        return "Error: The availability data file was not found."
    except KeyError as e:
        return f"Error: Missing expected column {e} in the dataset."
    except Exception as e:
        return f"Unexpected error: {str(e)}"
