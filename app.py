import os
from flask import Flask, render_template, request
import mysql.connector
import random

app = Flask(__name__)

# Database Configuration (Uses Environment Variables for Render, falls back to local for testing)
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'port': int(os.getenv('DB_PORT')) # Aiven uses custom ports, so this is important
}

def get_db_connection():
    # Added connection_timeout to prevent the app from hanging if the cloud DB is asleep
    return mysql.connector.connect(**DB_CONFIG, connection_timeout=10)

@app.route('/', methods=['GET', 'POST'])
def index():
    # 1. Grab parameters from the form, or set defaults for initial load
    locale = request.args.get('locale', 'en_US')
    
    # If no seed is provided, generate a random one to start
    default_seed = str(random.randint(1000, 9999))
    seed = request.args.get('seed', default_seed)
    
    users = []
    columns = []
    error = None

    # --- VALIDATION SECTION ---
    # Check if the user entered text instead of a number for the seed
    try:
        int(seed) # This will throw a ValueError if the seed contains letters
    except ValueError:
        error = "Invalid Input: The generation seed must be a number. Please try again."
        seed = default_seed # Reset the input box to a valid random number
    
    # Safely handle the page number just in case they manually type text in the URL
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
        
    batch_size = 15
    
    # Calculate the starting index for the stored procedure
    start_index = page - 1

    # 2. Connect to Database ONLY if there are no validation errors
    if not error:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True) # Returns rows as dictionaries
            
            # Call the Stored Procedure
            cursor.callproc('sp_generate_users_batch', [locale, seed, start_index, batch_size])
            
            # Fetch the results from the stored procedure
            for result in cursor.stored_results():
                users = result.fetchall()
                if users:
                    # Grab column names dynamically from the first row
                    columns = list(users[0].keys())
                break # Only need the first result set

            cursor.close()
            conn.close()

        except mysql.connector.Error as err:
            error = f"Database Error: {err}"
        except Exception as e:
            error = f"Application Error: {e}"

    # 3. Render the HTML page with the data
    return render_template('index.html', 
                           users=users, 
                           columns=columns, 
                           locale=locale, 
                           seed=seed, 
                           page=page,
                           error=error)

if __name__ == '__main__':
    # Run the app on port 5000. debug=True allows hot-reloading during development.
    # Note: Render will ignore this block and use Gunicorn instead.
    app.run(debug=True, host='0.0.0.0', port=5000)
