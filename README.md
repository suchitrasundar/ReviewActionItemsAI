# Document Review System

1. Project Overview
Goal: Reduce admin burden by automating the document review process for student action items. Show that by providing scoring the action items using an LLM and an algorithm, admins can automate this process. 
Prototype Purpose: Demonstrate how documents are uploaded, scored, and reviewed.


## Setup Instructions 

### Prerequisites

- Python 3.7 or higher
- pip 

### Step 1: Clone the Repository
>bash
git clone https://github.com/gurmesa/ReviewActionItemsAI.git
> cd ReviewActionItemsAI

### Step 2: Set Up a Virtual Environment
>bash
python3 -m venv venv
source venv/bin/activate

### Step 3: Install Dependencies
>bash
pip3 install -r requirements.txt

### Step 5: Set Up the Database

We are using SQLite, which doesn't require separate installation. The database will be created automatically when you run the application for the first time.

### Step 6: Run the Application
>bash
python3 app.py
