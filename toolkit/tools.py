import pandas as pd
from langchain_core.tools import tool
from data_models.models import *
from core.config import DoctorName, Specialization

def convert_to_am_pm(time):
    """Convert time from 24-hour format to 12-hour AM/PM format."""
    hour, minute = map(int, time.split(':'))
    period = 'AM' if hour < 12 else 'PM'
    hour = hour % 12
    hour = 12 if hour == 0 else hour
    return f"{hour}:{minute:02d} {period}"

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
    df= pd.read_csv("../data/doctor_availability.csv")
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
    df= pd.read_csv("../data/doctor_availability.csv")
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

@tool
def book_appointment(doctor_name: DoctorName, appointment_datetime: DateTimeModel, patient_id: IdentificationNumberModel):
    """
    Book an appointment with a specific doctor at a given validated date and time for a patient with a validated ID.
    
    Args:
        doctor_name (DoctorName): Name of the doctor (restricted set).
        appointment_datetime (DateTimeModel): Validated date-time string in format DD-MM-YYYY HH:MM.
        patient_id (IdentificationNumberModel): Validated patient ID (7 or 8 digit long).
    
    Returns:
        A confirmation message if the appointment is successfully booked or a message indicating unavailability.
    """
    df= pd.read_csv("../data/doctor_availability.csv")
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
        ] = [False,patient_id.id]

        df.to_csv("../data/doctor_availability.csv", index=False)
        return f"Appointment successfully booked with Dr. {doctor_name} on {appointment_datetime.datetime} for patient ID {patient_id.id}."
    else:
        return f"Sorry, Dr. {doctor_name} is not available on {appointment_datetime.datetime}. Please choose a different time."

@tool
def cancel_appointment(doctor_name: DoctorName, appointment_datetime: DateTimeModel, patient_id: IdentificationNumberModel):
    """
    Cancel an existing appointment with a specific doctor at a given validated date and time for a patient with a validated ID.
    
    Args:
        doctor_name (DoctorName): Name of the doctor (restricted set).
        appointment_datetime (DateTimeModel): Validated date-time string in format DD-MM-YYYY HH:MM.
        patient_id (IdentificationNumberModel): Validated patient ID (7 or 8 digit long).
    
    Returns:
        A confirmation message if the appointment is successfully canceled or a message indicating no such appointment exists.
    """
    df= pd.read_csv("../data/doctor_availability.csv")
    slot_str = f"{appointment_datetime.datetime}"
    appointment_exists = not df[
        (df['doctor_name'].str.lower() == doctor_name.lower()) & 
        (df['date_slot'] == slot_str) &
        (df['patient_to_attend'] == patient_id.id) &
        (df['is_available'] == False)
        ].empty
    
    if appointment_exists:
        df.loc[
            (df['doctor_name'].str.lower() == doctor_name.lower()) & 
            (df['date_slot'] == slot_str) &
            (df['patient_to_attend'] == patient_id.id), ['is_available','patient_to_attend']
        ] = [True, None]

        df.to_csv("../data/doctor_availability.csv", index=False)
        return f"Appointment with Dr. {doctor_name} on {appointment_datetime.datetime} for patient ID {patient_id.id} has been successfully canceled."
    else:
        return f"No existing appointment found with Dr. {doctor_name} on {appointment_datetime.datetime} for patient ID {patient_id.id}."
    

@tool
def reschedule_appointment(doctor_name: DoctorName, old_appointment_datetime: DateTimeModel, new_appointment_datetime: DateTimeModel, patient_id: IdentificationNumberModel):
    """
    Reschedule an existing appointment with a specific doctor from an old date and time to a new date and time for a patient with a validated ID.
    
    Args:
        doctor_name (DoctorName): Name of the doctor (restricted set).
        old_appointment_datetime (DateTimeModel): Validated old date-time string in format DD-MM-YYYY HH:MM.
        new_appointment_datetime (DateTimeModel): Validated new date-time string in format DD-MM-YYYY HH:MM.
        patient_id (IdentificationNumberModel): Validated patient ID (7 or 8 digit long).
    
    Returns:
        A confirmation message if the appointment is successfully rescheduled or a message indicating failure due to unavailability or no existing appointment.
    """
    df= pd.read_csv("../data/doctor_availability.csv")
    old_slot_str = f"{old_appointment_datetime.datetime}"
    new_slot_str = f"{new_appointment_datetime.datetime}"
    
    appointment_exists = not df[
        (df['doctor_name'].str.lower() == doctor_name.lower()) & 
        (df['date_slot'] == old_slot_str) &
        (df['patient_to_attend'] == patient_id.id) &
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
            (df['patient_to_attend'] == patient_id.id), ['is_available','patient_to_attend']
        ] = [True, None]
        
        # Book new appointment
        df.loc[
            (df['doctor_name'].str.lower() == doctor_name.lower()) & 
            (df['date_slot'] == new_slot_str), ['is_available','patient_to_attend']
        ] = [False, patient_id.id]

        df.to_csv("../data/doctor_availability.csv", index=False)
        return f"Appointment with Dr. {doctor_name} has been successfully rescheduled from {old_appointment_datetime.datetime} to {new_appointment_datetime.datetime} for patient ID {patient_id.id}."
    elif not appointment_exists:
        return f"No existing appointment found with Dr. {doctor_name} on {old_appointment_datetime.datetime} for patient ID {patient_id.id}."
    else:
        return f"Sorry, Dr. {doctor_name} is not available on {new_appointment_datetime.datetime}. Please choose a different time."
