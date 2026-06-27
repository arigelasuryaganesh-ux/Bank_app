import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, filedialog
import csv
import sqlite3
import hashlib
from datetime import datetime, timedelta
import os
import random
import string

# ==================== DATABASE SETUP ====================

class DatabaseManager:
    def __init__(self, db_name="bank_system.db"):
        self.db_name = db_name
        self.init_database()
    
    def init_database(self):
        """Initialize database and create tables if they don't exist"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                phone_number TEXT,
                balance DECIMAL(10,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                balance_after DECIMAL(10,2),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Loans table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                loan_type TEXT NOT NULL,
                principal DECIMAL(10,2) NOT NULL,
                interest_rate DECIMAL(5,2) NOT NULL,
                term_months INTEGER NOT NULL,
                monthly_payment DECIMAL(10,2) NOT NULL,
                total_payment DECIMAL(10,2) NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Deleted users history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deleted_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number TEXT,
                username TEXT,
                phone_number TEXT,
                balance DECIMAL(10,2),
                deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add account_number column if it doesn't exist (migration for existing databases)
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'account_number' not in columns:
            try:
                # Try to add the column (will work if table is empty)
                cursor.execute('ALTER TABLE users ADD COLUMN account_number TEXT UNIQUE')
            except sqlite3.OperationalError:
                # If table has data, add without UNIQUE constraint first
                cursor.execute('ALTER TABLE users ADD COLUMN account_number TEXT')
            
            # Assign account numbers to existing users
            cursor.execute('SELECT id FROM users WHERE account_number IS NULL')
            existing_users = cursor.fetchall()
            for user in existing_users:
                account_number = self.generate_account_number()
                cursor.execute('UPDATE users SET account_number = ? WHERE id = ?', 
                             (account_number, user[0]))

        if 'stored_password' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN stored_password TEXT')
            cursor.execute('UPDATE users SET stored_password = "" WHERE stored_password IS NULL')
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def validate_phone_number(self, phone_number):
        """Validate phone number - must be exactly 10 digits"""
        if not phone_number:
            return False, "Phone number is required"
        
        # Remove any spaces or special characters
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        
        if len(clean_phone) != 10:
            return False, "Phone number must be exactly 10 digits"
        
        return True, clean_phone
    
    def phone_number_exists(self, phone_number):
        """Check if phone number already exists in database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE phone_number = ?', (phone_number,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def generate_account_number(self):
        """Generate a unique account number"""
        # Format: ACC + 10 random digits
        random_digits = ''.join(random.choices(string.digits, k=10))
        account_number = f"ACC{random_digits}"
        
        # Ensure uniqueness
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT account_number FROM users WHERE account_number = ?', (account_number,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # Recursively generate a new one if duplicate
            return self.generate_account_number()
        
        return account_number
    
    def register_user(self, username, password, phone_number=""):
        """Register a new user and generate account number"""
        try:
            # Check if username already exists
            if self.user_exists(username):
                return False, "This username is already taken. Please choose a different username"
            
            # Validate phone number
            if phone_number:
                is_valid, phone_result = self.validate_phone_number(phone_number)
                if not is_valid:
                    return False, phone_result
                
                # Check if phone number already exists
                if self.phone_number_exists(phone_result):
                    return False, "This phone number is already registered with another account"
                
                phone_number = phone_result
            
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            hashed_password = self.hash_password(password)
            account_number = self.generate_account_number()
            
            cursor.execute('''
                INSERT INTO users (account_number, username, password, stored_password, phone_number, balance)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (account_number, username, hashed_password, password, phone_number, 0.0))
            conn.commit()
            conn.close()
            return True, account_number
        except sqlite3.IntegrityError as e:
            return False, f"Registration failed: {str(e)}"
    
    def validate_user(self, username, password):
        """Validate user credentials"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        hashed_password = self.hash_password(password)
        
        cursor.execute('SELECT id FROM users WHERE username = ? AND password = ?',
                      (username, hashed_password))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def get_user_id(self, username):
        """Get user ID by username"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def user_exists(self, username):
        """Check if user exists"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def get_balance(self, username):
        """Get user balance"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    
    def get_account_number(self, username):
        """Get user's account number"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT account_number FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_user_phone_number(self, username):
        """Get user's phone number"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT phone_number FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def reset_password(self, username, phone_number, new_password):
        """Reset user password if phone number matches"""
        if not self.user_exists(username):
            return False, "User not found"

        stored_phone = self.get_user_phone_number(username)
        if not stored_phone or stored_phone != phone_number:
            return False, "Phone number does not match our records"

        hashed_password = self.hash_password(new_password)
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password = ?, stored_password = ? WHERE username = ?',
                       (hashed_password, new_password, username))
        conn.commit()
        conn.close()
        return True, "Password reset successful"
    
    def deposit(self, username, amount):
        """Deposit money to user account"""
        if amount <= 0:
            return False, "Amount must be greater than 0"
        
        user_id = self.get_user_id(username)
        if not user_id:
            return False, "User not found"
        
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Get current balance
            cursor.execute('SELECT balance FROM users WHERE id = ?', (user_id,))
            current_balance = cursor.fetchone()[0]
            new_balance = current_balance + amount
            
            # Update balance
            cursor.execute('UPDATE users SET balance = ? WHERE id = ?',
                          (new_balance, user_id))
            
            # Record transaction
            cursor.execute('''
                INSERT INTO transactions (user_id, transaction_type, amount, balance_after)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 'DEPOSIT', amount, new_balance))
            
            conn.commit()
            conn.close()
            return True, f"Deposit successful! New balance: ${new_balance:.2f}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def withdraw(self, username, amount):
        """Withdraw money from user account"""
        if amount <= 0:
            return False, "Amount must be greater than 0"
        
        user_id = self.get_user_id(username)
        if not user_id:
            return False, "User not found"
        
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Get current balance
            cursor.execute('SELECT balance FROM users WHERE id = ?', (user_id,))
            current_balance = cursor.fetchone()[0]
            
            if current_balance < amount:
                conn.close()
                return False, f"Insufficient Balance! Available: ${current_balance:.2f}"
            
            new_balance = current_balance - amount
            
            # Update balance
            cursor.execute('UPDATE users SET balance = ? WHERE id = ?',
                          (new_balance, user_id))
            
            # Record transaction
            cursor.execute('''
                INSERT INTO transactions (user_id, transaction_type, amount, balance_after)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 'WITHDRAW', amount, new_balance))
            
            conn.commit()
            conn.close()
            return True, f"Withdrawal successful! New balance: ${new_balance:.2f}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def calculate_loan_details(self, principal, annual_rate, term_months):
        """Calculate monthly and total payment for a loan."""
        if principal <= 0 or term_months <= 0:
            return 0.0, 0.0

        monthly_rate = annual_rate / 100.0 / 12.0
        if monthly_rate == 0:
            monthly_payment = principal / term_months
        else:
            factor = (1 + monthly_rate) ** term_months
            monthly_payment = principal * monthly_rate * factor / (factor - 1)

        total_payment = monthly_payment * term_months
        return round(monthly_payment, 2), round(total_payment, 2)

    def get_loan_offers(self):
        """Return current loan offers with interest rates."""
        return [
            {"type": "Personal Loan", "rate": 12.0, "min_amount": 500, "max_amount": 50000, "terms": [12, 24, 36]},
            {"type": "Home Loan", "rate": 7.5, "min_amount": 5000, "max_amount": 500000, "terms": [120, 180, 240]},
            {"type": "Car Loan", "rate": 9.2, "min_amount": 1000, "max_amount": 100000, "terms": [24, 36, 48]},
        ]

    def apply_loan(self, username, loan_type, principal, term_months):
        """Apply loan and credit amount to user balance."""
        if principal <= 0:
            return False, "Loan amount must be greater than zero"
        if term_months <= 0:
            return False, "Loan term must be greater than zero months"

        user_id = self.get_user_id(username)
        if not user_id:
            return False, "User not found"

        offers = self.get_loan_offers()
        offer = next((offer for offer in offers if offer["type"] == loan_type), None)
        if not offer:
            return False, "Selected loan type is not available"

        if principal < offer["min_amount"] or principal > offer["max_amount"]:
            return False, f"Loan amount must be between ${offer['min_amount']:.2f} and ${offer['max_amount']:.2f}"
        if term_months not in offer["terms"]:
            return False, f"Available terms for {loan_type} are: {', '.join(str(t) for t in offer['terms'])} months"

        monthly_payment, total_payment = self.calculate_loan_details(principal, offer["rate"], term_months)

        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            cursor.execute('SELECT balance FROM users WHERE id = ?', (user_id,))
            current_balance = cursor.fetchone()[0]
            new_balance = current_balance + principal
            cursor.execute('UPDATE users SET balance = ? WHERE id = ?', (new_balance, user_id))

            cursor.execute('''
                INSERT INTO loans (user_id, loan_type, principal, interest_rate, term_months, monthly_payment, total_payment, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, loan_type, principal, offer["rate"], term_months, monthly_payment, total_payment, 'ACTIVE'))

            cursor.execute('''
                INSERT INTO transactions (user_id, transaction_type, amount, balance_after)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 'LOAN_DISBURSED', principal, new_balance))

            conn.commit()
            conn.close()
            return True, (f"Loan approved! {loan_type} of ${principal:.2f} disbursed at {offer['rate']:.2f}% APR. "
                          f"Monthly payment: ${monthly_payment:.2f} for {term_months} months. "
                          f"Total repayment: ${total_payment:.2f}.")
        except Exception as e:
            return False, f"Error applying loan: {str(e)}"

    def get_loan_history(self, username):
        """Get loan history for a user."""
        user_id = self.get_user_id(username)
        if not user_id:
            return []

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT loan_type, principal, interest_rate, term_months, monthly_payment, total_payment, status, applied_at
            FROM loans WHERE user_id = ? ORDER BY applied_at DESC
        ''', (user_id,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_transaction_history(self, username):
        """Get transaction history for user"""
        user_id = self.get_user_id(username)
        if not user_id:
            return []
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, transaction_type, amount, balance_after, timestamp
            FROM transactions WHERE user_id = ?
            ORDER BY timestamp DESC LIMIT 10
        ''', (user_id,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_all_transactions(self, username):
        """Return all transactions for a user (no limit)."""
        user_id = self.get_user_id(username)
        if not user_id:
            return []

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, transaction_type, amount, balance_after, timestamp
            FROM transactions WHERE user_id = ?
            ORDER BY timestamp DESC
        ''', (user_id,))
        results = cursor.fetchall()
        conn.close()
        return results
    
    def search_user(self, username):
        """Search for user by username"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, account_number, username, balance, created_at, stored_password
            FROM users WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        conn.close()
        return result

    def get_all_users(self):
        """Return all registered users."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, account_number, username, balance, created_at, stored_password
            FROM users ORDER BY created_at DESC
        ''')
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_active_user_count(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_deleted_user_count(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM deleted_users')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_total_user_count(self):
        return self.get_active_user_count() + self.get_deleted_user_count()

    def delete_user(self, username):
        """Delete a user and their transactions."""
        user_id = self.get_user_id(username)
        if not user_id:
            return False, "User not found"

        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('SELECT account_number, username, phone_number, balance FROM users WHERE id = ?', (user_id,))
            user_data = cursor.fetchone()
            if user_data:
                cursor.execute('''
                    INSERT INTO deleted_users (account_number, username, phone_number, balance)
                    VALUES (?, ?, ?, ?)
                ''', (user_data[0], user_data[1], user_data[2], user_data[3]))

            cursor.execute('DELETE FROM transactions WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True, "User deleted successfully"
        except Exception as e:
            return False, f"Error deleting user: {str(e)}"
    ### 
    # -------------------- Utility --------------------
    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def create_header(self, text):
        tk.Label(self.root, text=text,
                 font=("Arial", 18, "bold"),
                 bg=self.bg_color,
                 fg="white").pack(fill="x")

    # -------------------- Animation --------------------
    def add_animation(self):
        canvas = tk.Canvas(self.root, width=200, height=150, bg="white")
        canvas.pack(pady=10)

        coin = canvas.create_oval(90, 10, 110, 30, fill="gold")

        def animate():
            def step():
                canvas.move(coin, 0, 5)
                pos = canvas.coords(coin)
                if pos[3] < 140:
                    self.root.after(30, step)
            step()

        tk.Button(self.root, text="💰 Show Animation",
                  command=animate,
                  bg="#10b981", fg="white").pack()

# ==================== GUI APPLICATION ====================

class BankingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("New AI BANK")
        self.root.geometry("1000x700")
        self.root.minsize(900, 650)
        self.root.configure(bg="#f0f2f5")
        
        # Enable window resizing and maximize button
        self.root.resizable(True, True)
        
        self.db = DatabaseManager()
        self.current_user = None
        self.delete_lockouts = {}
        self.delete_lockout_hours = 24
        
        # Configure styles
        self.setup_styles()
        
        # Show main page
        self.show_main_page()
    
    def setup_styles(self):
        """Setup custom styles"""
        self.bg_color = "#f0f2f5"
        self.primary_color = "#1e40af"
        self.success_color = "#16a34a"
        self.danger_color = "#dc2626"
        self.card_bg = "#ffffff"
        self.text_color = "#1f2937"
        self.border_color = "#e5e7eb"

    def get_delete_lockout_state(self, username):
        state = self.delete_lockouts.get(username)
        if state is None:
            state = {"attempts": 0, "lockout_until": None}
            self.delete_lockouts[username] = state
        return state

    def is_delete_locked_out(self, username):
        state = self.get_delete_lockout_state(username)
        lockout_until = state.get("lockout_until")
        if lockout_until is None:
            return False
        if datetime.now() >= lockout_until:
            state["attempts"] = 0
            state["lockout_until"] = None
            return False
        return True

    def get_delete_lockout_remaining(self, username):
        if not self.is_delete_locked_out(username):
            return 0, 0
        state = self.get_delete_lockout_state(username)
        delta = state["lockout_until"] - datetime.now()
        total_seconds = max(int(delta.total_seconds()), 0)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return hours, minutes

    def increment_delete_attempt(self, username):
        state = self.get_delete_lockout_state(username)
        state["attempts"] += 1
        if state["attempts"] >= 3:
            state["lockout_until"] = datetime.now() + timedelta(hours=self.delete_lockout_hours)
            return state["attempts"], True
        return state["attempts"], False
    
    def clear_window(self):
        """Clear all widgets from window"""
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def create_header(self, title="New AI BANK"):
        """Create header frame"""
        header = tk.Frame(self.root, bg=self.primary_color, height=80)
        header.pack(fill=tk.X)
        
        title_label = tk.Label(header, text=title, font=("Arial", 28, "bold"),
                               fg="white", bg=self.primary_color)
        title_label.pack(pady=15)
        
        if self.current_user:
            user_label = tk.Label(header, text=f"Welcome, {self.current_user}",
                                 font=("Arial", 10), fg="#e5e7eb", bg=self.primary_color)
            user_label.pack()
        
        return header

    def create_split_card(self, left_emoji="💰", left_title=None, left_subtitle=None,
                          card_width=760, card_height=420, parent=None):
        """Create a centered split card with an illustration panel on the left and a form area on the right.

        Returns the `form` frame where callers can add inputs and buttons.
        """
        container_parent = parent if parent is not None else self.root
        form_container = tk.Frame(container_parent, bg=self.bg_color)
        form_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=30)

        card = tk.Frame(form_container, bg="#ffffff", bd=0, relief=tk.FLAT,
                        highlightbackground="#e6edf8", highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        inner = tk.Frame(card, bg="#ffffff")
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        left = tk.Frame(inner, bg="#eef6ff", width=220)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        tk.Label(left, text=left_emoji, font=("Arial", 48), bg="#eef6ff", fg="#0b5ed7").pack(pady=(28, 6))
        if left_title:
            tk.Label(left, text=left_title, font=("Arial", 12, "bold"), fg="#0b5ed7", bg="#eef6ff").pack()
        if left_subtitle:
            tk.Label(left, text=left_subtitle, font=("Arial", 9), fg="#475569", bg="#eef6ff",
                     wraplength=180, justify=tk.CENTER).pack(padx=10, pady=(6, 0))

        form = tk.Frame(inner, bg="#ffffff")
        form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 6))
        return form
    
    
    def show_main_page(self):
        """Show main landing page"""
        self.clear_window()
        self.current_user = None
        
        # Top banner with logo
        banner = tk.Frame(self.root, bg=self.primary_color, height=100)
        banner.pack(fill=tk.X)
        
        # Logo and title
        logo_frame = tk.Frame(banner, bg=self.primary_color)
        logo_frame.pack(pady=15)
        
        tk.Label(logo_frame, text="🏦", font=("Arial", 40), bg=self.primary_color).pack(side=tk.LEFT, padx=10)
        
        title_frame = tk.Frame(logo_frame, bg=self.primary_color)
        title_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(title_frame, text="New AI BANK", font=("Arial", 28, "bold"),
                fg="white", bg=self.primary_color).pack(anchor=tk.W)
        tk.Label(title_frame, text="Your Trusted Financial Partner", font=("Arial", 10),
                fg="#dbeafe", bg=self.primary_color).pack(anchor=tk.W)

        total_users = self.db.get_total_user_count()
        active_users = self.db.get_active_user_count()
        deleted_users = self.db.get_deleted_user_count()

        # Marquee ad banner below the top title
        marquee_frame = tk.Frame(self.root, bg="#fde68a", height=40)
        marquee_frame.pack(fill=tk.X)
        marquee_label = tk.Label(marquee_frame, text=f"Helpline: 1800-123-4567 | Special: Get fast loan approval with low interest rates — apply now at New AI BANK!",
                                 font=("Arial", 11, "bold"), fg="#92400e", bg="#fde68a")
        marquee_label.place(x=0, rely=0.5, anchor="w")

        def animate_marquee():
            if not marquee_label.winfo_exists() or not marquee_frame.winfo_exists():
                return
            marquee_frame.update_idletasks()
            x = marquee_label.winfo_x()
            if x + marquee_label.winfo_width() < 0:
                x = marquee_frame.winfo_width()
            marquee_label.place(x=x-2, rely=0.5, anchor="w")
            marquee_frame.after(30, animate_marquee)

        self.root.after(100, animate_marquee)

        # Main container with scroll support
        outer_frame = tk.Frame(self.root, bg=self.bg_color)
        outer_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        canvas = tk.Canvas(outer_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        main_container = tk.Frame(canvas, bg=self.bg_color)
        window_id = canvas.create_window((0, 0), window=main_container, anchor="nw")

        def update_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(window_id, width=canvas.winfo_width())

        def on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, 'num', None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, 'num', None) == 5:
                canvas.yview_scroll(1, "units")

        main_container.bind("<Configure>", update_scrollregion)
        canvas.bind('<Configure>', update_scrollregion)
        canvas.bind('<Enter>', lambda event: canvas.focus_set())
        canvas.bind_all('<MouseWheel>', on_mousewheel)
        canvas.bind_all('<Button-4>', on_mousewheel)
        canvas.bind_all('<Button-5>', on_mousewheel)

        # Main content and stats card
        stats_card = tk.Frame(main_container, bg="#eef2ff", relief=tk.RIDGE, bd=1)
        stats_card.pack(pady=(10, 20), fill=tk.X, padx=10)

        tk.Label(stats_card, text=f"Total users: {total_users}", font=("Arial", 10, "bold"),
                fg="#1e3a8a", bg="#eef2ff").pack(side=tk.LEFT, padx=(20, 15), pady=15)
        tk.Label(stats_card, text=f"Active users: {active_users}", font=("Arial", 10, "bold"),
                fg="#1e3a8a", bg="#eef2ff").pack(side=tk.LEFT, padx=(0, 15), pady=15)
        tk.Label(stats_card, text=f"Deleted users: {deleted_users}", font=("Arial", 10, "bold"),
                fg="#1e3a8a", bg="#eef2ff").pack(side=tk.LEFT, pady=15)

        # Welcome section
        welcome_frame = tk.Frame(main_container, bg=self.card_bg, relief=tk.FLAT)
        welcome_frame.pack(pady=0, fill=tk.X)

        tk.Label(welcome_frame, text="Welcome to New AI BANK", font=("Arial", 16, "bold"),
                fg=self.primary_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        tk.Label(welcome_frame, text="Manage your finances with ease. Choose an option below to get started.",
                font=("Arial", 10), fg="#6b7280", bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(0, 15))

        # Promotions section
        promo_frame = tk.Frame(main_container, bg=self.bg_color)
        promo_frame.pack(pady=(0, 20), fill=tk.X)

        promo_card_1 = tk.Frame(promo_frame, bg="#eef2ff", relief=tk.RIDGE, bd=1)
        promo_card_1.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
        tk.Label(promo_card_1, text="🔥 Special Loan Offers", font=("Arial", 12, "bold"),
                fg="#1e3a8a", bg="#eef2ff").pack(anchor=tk.W, padx=15, pady=(15, 5))
        tk.Label(promo_card_1, text="Apply for personal, car, and home loans with low APR and quick approval.",
                font=("Arial", 9), fg="#374151", bg="#eef2ff", wraplength=260, justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=(0, 15))

        promo_card_2 = tk.Frame(promo_frame, bg="#dcfce7", relief=tk.RIDGE, bd=1)
        promo_card_2.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
        tk.Label(promo_card_2, text="💰 High Savings Rates", font=("Arial", 12, "bold"),
                fg="#166534", bg="#dcfce7").pack(anchor=tk.W, padx=15, pady=(15, 5))
        tk.Label(promo_card_2, text="Grow your savings with our competitive interest plans and secure returns.",
                font=("Arial", 9), fg="#374151", bg="#dcfce7", wraplength=260, justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=(0, 15))

        promo_card_3 = tk.Frame(promo_frame, bg="#fee2e2", relief=tk.RIDGE, bd=1)
        promo_card_3.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
        tk.Label(promo_card_3, text="🛡️ Secure Banking", font=("Arial", 12, "bold"),
                fg="#991b1b", bg="#fee2e2").pack(anchor=tk.W, padx=15, pady=(15, 5))
        tk.Label(promo_card_3, text="Bank with confidence: 24/7 protection, support, and reliable transaction monitoring.",
                font=("Arial", 9), fg="#374151", bg="#fee2e2", wraplength=260, justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=(0, 15))

        balance_action_frame = tk.Frame(main_container, bg=self.bg_color)
        balance_action_frame.pack(pady=(0, 10), fill=tk.X)
        
        tk.Button(balance_action_frame, text="Check Balance", command=self.show_balance_page,
                  font=("Arial", 12, "bold"), bg="#8b5cf6", fg="white",
                  padx=30, pady=10, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=20)
        tk.Button(balance_action_frame, text="Reset Password", command=self.show_reset_password_page,
                  font=("Arial", 12, "bold"), bg="#ef4444", fg="white",
                  padx=30, pady=10, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=20)
        
        # Features section
        features_frame = tk.Frame(main_container, bg=self.bg_color)
        features_frame.pack(pady=20, fill=tk.BOTH, expand=True)
        
        # Row 1 - 3 buttons
        row1 = tk.Frame(features_frame, bg=self.bg_color)
        row1.pack(pady=15, fill=tk.BOTH, expand=True)
        
        # Signup Card
        signup_card = tk.Frame(row1, bg=self.card_bg, relief=tk.RAISED, bd=1)
        signup_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(signup_card, text="✏️", font=("Arial", 30), bg=self.card_bg).pack(pady=10)
        tk.Label(signup_card, text="New User Signup", font=("Arial", 12, "bold"),
                fg=self.text_color, bg=self.card_bg).pack()
        tk.Label(signup_card, text="Create a new account", font=("Arial", 9),
                fg="#9ca3af", bg=self.card_bg).pack(pady=(0, 10))
        
        signup_btn = tk.Button(signup_card, text="Signup", command=self.show_signup_page,
                              font=("Arial", 10, "bold"), fg="white", bg="#6366f1",
                              padx=20, pady=8, relief=tk.FLAT, cursor="hand2")
        signup_btn.pack(pady=(0, 10))
        
        # Login Card
        login_card = tk.Frame(row1, bg=self.card_bg, relief=tk.RAISED, bd=1)
        login_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(login_card, text="🔐", font=("Arial", 30), bg=self.card_bg).pack(pady=10)
        tk.Label(login_card, text="User Login", font=("Arial", 12, "bold"),
                fg=self.text_color, bg=self.card_bg).pack()
        tk.Label(login_card, text="Sign in to your account", font=("Arial", 9),
                fg="#9ca3af", bg=self.card_bg).pack(pady=(0, 10))
        
        login_btn = tk.Button(login_card, text="Login", command=self.show_login_page,
                             font=("Arial", 10, "bold"), fg="white", bg="#3b82f6",
                             padx=20, pady=8, relief=tk.FLAT, cursor="hand2")
        login_btn.pack(pady=(0, 10))
        
        # Deposit Card
        deposit_card = tk.Frame(row1, bg=self.card_bg, relief=tk.RAISED, bd=1)
        deposit_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(deposit_card, text="💰", font=("Arial", 30), bg=self.card_bg).pack(pady=10)
        tk.Label(deposit_card, text="Deposit Money", font=("Arial", 12, "bold"),
                fg=self.text_color, bg=self.card_bg).pack()
        tk.Label(deposit_card, text="Add funds to your account", font=("Arial", 9),
                fg="#9ca3af", bg=self.card_bg).pack(pady=(0, 10))
        
        deposit_btn = tk.Button(deposit_card, text="Deposit", command=self.show_deposit_page,
                               font=("Arial", 10, "bold"), fg="white", bg="#10b981",
                               padx=20, pady=8, relief=tk.FLAT, cursor="hand2")
        deposit_btn.pack(pady=(0, 10))
        
        # Row 2 - 2 buttons
        row2 = tk.Frame(features_frame, bg=self.bg_color)
        row2.pack(pady=15, fill=tk.BOTH, expand=True)

        # Withdraw Card
        withdraw_card = tk.Frame(row2, bg=self.card_bg, relief=tk.RAISED, bd=1)
        withdraw_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)

        tk.Label(withdraw_card, text="💸", font=("Arial", 30), bg=self.card_bg).pack(pady=10)
        tk.Label(withdraw_card, text="Withdraw Money", font=("Arial", 12, "bold"),
                fg=self.text_color, bg=self.card_bg).pack()
        tk.Label(withdraw_card, text="Withdraw from your account", font=("Arial", 9),
                fg="#9ca3af", bg=self.card_bg).pack(pady=(0, 10))

        withdraw_btn = tk.Button(withdraw_card, text="Withdraw", command=self.show_withdraw_page,
                                font=("Arial", 10, "bold"), fg="white", bg="#f59e0b",
                                padx=20, pady=8, relief=tk.FLAT, cursor="hand2")
        withdraw_btn.pack(pady=(0, 10))

        # Search Card
        search_card = tk.Frame(row2, bg=self.card_bg, relief=tk.RAISED, bd=1)
        search_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)

        tk.Label(search_card, text="🔍", font=("Arial", 30), bg=self.card_bg).pack(pady=10)
        tk.Label(search_card, text="Search User", font=("Arial", 12, "bold"),
                fg=self.text_color, bg=self.card_bg).pack()
        tk.Label(search_card, text="Find user accounts & details", font=("Arial", 9),
                fg="#9ca3af", bg=self.card_bg).pack(pady=(0, 10))

        search_btn = tk.Button(search_card, text="Search", command=self.show_search_page,
                              font=("Arial", 10, "bold"), fg="white", bg="#ec4899",
                              padx=20, pady=8, relief=tk.FLAT, cursor="hand2")
        search_btn.pack(pady=(0, 10))

        # Row 3 - 2 buttons
        row3 = tk.Frame(features_frame, bg=self.bg_color)
        row3.pack(pady=15, fill=tk.BOTH, expand=True)

        # Balance Card
        balance_card = tk.Frame(row3, bg=self.card_bg, relief=tk.RAISED, bd=1)
        balance_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(balance_card, text="💳", font=("Arial", 30), bg=self.card_bg).pack(pady=10)
        tk.Label(balance_card, text="Check Balance", font=("Arial", 12, "bold"),
                fg=self.text_color, bg=self.card_bg).pack()
        tk.Label(balance_card, text="View your account balance & history", font=("Arial", 9),
                fg="#9ca3af", bg=self.card_bg).pack(pady=(0, 10))
        
        balance_btn = tk.Button(balance_card, text="Check Balance", command=self.show_balance_page,
                               font=("Arial", 10, "bold"), fg="white", bg="#8b5cf6",
                               padx=20, pady=8, relief=tk.FLAT, cursor="hand2")
        balance_btn.pack(pady=(0, 10))

        # Loan Offers Card
        loan_card = tk.Frame(row3, bg=self.card_bg, relief=tk.RAISED, bd=1)
        loan_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)

        tk.Label(loan_card, text="📈", font=("Arial", 30), bg=self.card_bg).pack(pady=10)
        tk.Label(loan_card, text="Loan Offers", font=("Arial", 12, "bold"),
                fg=self.text_color, bg=self.card_bg).pack()
        tk.Label(loan_card, text="Apply for loans with competitive rates", font=("Arial", 9),
                fg="#9ca3af", bg=self.card_bg).pack(pady=(0, 10))

        loan_btn = tk.Button(loan_card, text="View Loans", command=self.show_loan_offers_page,
                              font=("Arial", 10, "bold"), fg="white", bg="#f97316",
                              padx=20, pady=8, relief=tk.FLAT, cursor="hand2")
        loan_btn.pack(pady=(0, 10))
        
        # Footer info
        footer = tk.Frame(main_container, bg=self.card_bg, relief=tk.FLAT)
        footer.pack(pady=20, fill=tk.X)
        
        tk.Label(footer, text="✓ Secure Banking  •  ✓ 24/7 Access  •  ✓ Fast Transactions  •  ✓ Easy Management",
                font=("Arial", 9), fg="#6b7280", bg=self.card_bg).pack(padx=20, pady=10)
    
    def create_card_button(self, parent, text, command, color):
        """Create a card-style button"""
        btn = tk.Button(parent, text=text, command=command,
                       font=("Arial", 14, "bold"), fg="white", bg=color,
                       padx=30, pady=15, relief=tk.FLAT, cursor="hand2",
                       activebackground=color, activeforeground="white")
        return btn

    def show_big_popup(self, title, message, amount_text=None, success=True):
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.configure(bg="#e0e7ff")
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False, False)
        popup.geometry("460x260")

        popup_card = tk.Frame(popup, bg="#ffffff", bd=0,
                              highlightbackground="#c7d2fe", highlightthickness=1)
        popup_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        icon = "✅" if success else "⚠️"
        header = tk.Frame(popup_card, bg=self.primary_color, height=70)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"{icon} {title}", font=("Arial", 14, "bold"), fg="white", bg=self.primary_color).pack(anchor=tk.W, padx=20, pady=15)

        body = tk.Frame(popup_card, bg="#f8fafc")
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tk.Label(body, text=message, font=("Arial", 12), fg=self.text_color,
                bg="#f8fafc", wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 12))
        if amount_text:
            tk.Label(body, text=amount_text, font=("Arial", 24, "bold"), fg=self.primary_color,
                    bg="#eff6ff", padx=14, pady=10).pack(anchor=tk.CENTER, pady=(0, 14))

        tk.Button(body, text="OK", command=popup.destroy,
                  font=("Arial", 12, "bold"), bg=self.primary_color, fg="white",
                  padx=24, pady=10, relief=tk.FLAT, activebackground="#2563eb").pack(pady=(5, 0))

        self.root.wait_window(popup)

    def show_login_page(self):
        """Show user login page"""
        self.clear_window()
        self.create_header("User Login")
        
        # Split card layout
        card = self.create_split_card(left_emoji="🔐", left_title="Secure Login",
                          left_subtitle="Access your account securely")

        tk.Label(card, text="Secure Login", font=("Arial", 18, "bold"),
                fg=self.primary_color, bg="#ffffff").pack(anchor=tk.W, padx=20, pady=(0, 5))
        tk.Label(card, text="Enter your credentials to access your account, view balance, and manage funds.",
                font=("Arial", 10), fg="#6b7280", bg="#ffffff", wraplength=520, justify=tk.LEFT).pack(anchor=tk.W, padx=20, pady=(0, 15))
        
        # Username
        tk.Label(card, text="Username", font=("Arial", 10, "bold"),
                fg=self.text_color, bg="#ffffff").pack(anchor=tk.W, padx=20, pady=(5, 5))
        username_entry = tk.Entry(card, font=("Arial", 10), width=24, bd=0, relief=tk.FLAT,
                                  bg="#f8fafc", highlightthickness=1, highlightbackground="#d1d5db",
                                  highlightcolor=self.primary_color)
        username_entry.pack(padx=20, pady=2, ipady=2)
        
        # Password
        tk.Label(card, text="Password", font=("Arial", 10, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 3))
        password_frame = tk.Frame(card, bg=self.card_bg)
        password_frame.pack(padx=20, pady=2, fill=tk.X)

        password_entry = tk.Entry(password_frame, font=("Arial", 10), width=20, show="*")
        password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

        password_visible = tk.BooleanVar(value=False)
        def toggle_password_visibility():
            visible = not password_visible.get()
            password_visible.set(visible)
            if visible:
                password_entry.config(show="")
                toggle_btn.config(text="🙈")
            else:
                password_entry.config(show="*")
                toggle_btn.config(text="👁️")

        toggle_btn = tk.Button(password_frame, text="👁️", command=toggle_password_visibility,
                               font=("Arial", 10), bg=self.card_bg, fg=self.text_color,
                               bd=0, activebackground=self.card_bg, cursor="hand2")
        toggle_btn.pack(side=tk.LEFT, padx=(5, 0), ipady=4)
        
        # Phone Number
        tk.Label(card, text="Phone Number (for new users)", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=15, pady=(15, 5))
        phone_entry = tk.Entry(card, font=("Arial", 11), width=28)
        phone_entry.pack(padx=15, pady=3)
        
        # Buttons frame
        btn_frame = tk.Frame(card, bg=self.card_bg)
        btn_frame.pack(pady=30)
        
        def login_action():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            phone_number = phone_entry.get().strip()
            
            if not username or not password:
                messagebox.showerror("Error", "Please enter username and password")
                return
            
            if not self.db.user_exists(username):
                # Register new user
                if phone_number:
                    # Validate phone number
                    is_valid, result = self.db.validate_phone_number(phone_number)
                    if not is_valid:
                        messagebox.showerror("Error", result)
                        return
                    
                    # Check if phone already exists
                    if self.db.phone_number_exists(result):
                        messagebox.showerror("Error", "This phone number is already registered with another account")
                        return
                    
                    success, account_number = self.db.register_user(username, password, result)
                    if success:
                        messagebox.showinfo("Success", f"User {username} registered successfully!\nAccount Number: {account_number}\nPhone: {result}\nInitial balance: $0.00")
                        self.current_user = username
                        self.show_dashboard()
                    else:
                        messagebox.showerror("Error", account_number if isinstance(account_number, str) else "Registration failed")
                else:
                    messagebox.showerror("Error", "Phone number is required for new users")
            else:
                # Validate existing user
                if self.db.validate_user(username, password):
                    messagebox.showinfo("Success", "Login Successful!")
                    self.current_user = username
                    self.show_dashboard()
                else:
                    messagebox.showerror("Error", "Invalid username or password")
        
        login_btn = tk.Button(btn_frame, text="Login", command=login_action,
                             font=("Arial", 12, "bold"), bg=self.primary_color,
                             fg="white", padx=40, pady=10, relief=tk.FLAT)
        login_btn.pack(side=tk.LEFT, padx=10)
        
        back_btn = tk.Button(btn_frame, text="Back", command=self.show_main_page,
                            font=("Arial", 12, "bold"), bg="#9ca3af",
                            fg="white", padx=40, pady=10, relief=tk.FLAT)
        back_btn.pack(side=tk.LEFT, padx=10)

    def show_reset_password_page(self):
        """Show password reset page"""
        self.clear_window()
        self.create_header("Reset Password")

        form_container = tk.Frame(self.root, bg=self.bg_color)
        form_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=40)

        card = tk.Frame(form_container, bg=self.card_bg, relief=tk.FLAT)
        card.pack(pady=20, padx=50)

        tk.Label(card, text="Username", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(20, 5))
        username_entry = tk.Entry(card, font=("Arial", 11), width=40)
        username_entry.pack(padx=20, pady=5)

        tk.Label(card, text="Registered Phone Number", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        phone_entry = tk.Entry(card, font=("Arial", 11), width=40)
        phone_entry.pack(padx=20, pady=5)

        tk.Label(card, text="New Password", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        new_password_frame = tk.Frame(card, bg=self.card_bg)
        new_password_frame.pack(padx=20, pady=5, fill=tk.X)
        new_password_entry = tk.Entry(new_password_frame, font=("Arial", 11), width=34, show="*")
        new_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        new_password_visible = tk.BooleanVar(value=False)
        def toggle_new_password():
            visible = not new_password_visible.get()
            new_password_visible.set(visible)
            if visible:
                new_password_entry.config(show="")
                new_pwd_toggle.config(text="🙈")
            else:
                new_password_entry.config(show="*")
                new_pwd_toggle.config(text="👁️")
        new_pwd_toggle = tk.Button(new_password_frame, text="👁️", command=toggle_new_password,
                                   font=("Arial", 10), bg=self.card_bg, fg=self.text_color,
                                   bd=0, activebackground=self.card_bg, cursor="hand2")
        new_pwd_toggle.pack(side=tk.LEFT, padx=(5, 0))

        tk.Label(card, text="Confirm New Password", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        confirm_password_frame = tk.Frame(card, bg=self.card_bg)
        confirm_password_frame.pack(padx=20, pady=5, fill=tk.X)
        confirm_password_entry = tk.Entry(confirm_password_frame, font=("Arial", 11), width=34, show="*")
        confirm_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        confirm_password_visible = tk.BooleanVar(value=False)
        def toggle_confirm_password():
            visible = not confirm_password_visible.get()
            confirm_password_visible.set(visible)
            if visible:
                confirm_password_entry.config(show="")
                confirm_pwd_toggle.config(text="🙈")
            else:
                confirm_password_entry.config(show="*")
                confirm_pwd_toggle.config(text="👁️")
        confirm_pwd_toggle = tk.Button(confirm_password_frame, text="👁️", command=toggle_confirm_password,
                                       font=("Arial", 10), bg=self.card_bg, fg=self.text_color,
                                       bd=0, activebackground=self.card_bg, cursor="hand2")
        confirm_pwd_toggle.pack(side=tk.LEFT, padx=(5, 0))

        btn_frame = tk.Frame(card, bg=self.card_bg)
        btn_frame.pack(pady=30)

        def reset_action():
            username = username_entry.get().strip()
            phone_number = phone_entry.get().strip()
            new_password = new_password_entry.get().strip()
            confirm_password = confirm_password_entry.get().strip()

            if not username or not phone_number or not new_password or not confirm_password:
                messagebox.showerror("Error", "Please fill all required fields")
                return

            if new_password != confirm_password:
                messagebox.showerror("Error", "Passwords do not match")
                return

            if len(new_password) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters long")
                return

            success, message = self.db.reset_password(username, phone_number, new_password)
            if success:
                messagebox.showinfo("Success", message)
                self.show_main_page()
            else:
                messagebox.showerror("Error", message)

        reset_btn = tk.Button(btn_frame, text="Reset Password", command=reset_action,
                              font=("Arial", 12, "bold"), bg="#ef4444",
                              fg="white", padx=40, pady=10, relief=tk.FLAT)
        reset_btn.pack(side=tk.LEFT, padx=10)

        back_btn = tk.Button(btn_frame, text="Back", command=self.show_main_page,
                              font=("Arial", 12, "bold"), bg="#9ca3af",
                              fg="white", padx=40, pady=10, relief=tk.FLAT)
        back_btn.pack(side=tk.LEFT, padx=10)

    def show_signup_page(self):
        """Show user signup page for new users"""
        self.clear_window()
        self.create_header("Create New Account")
        
        # Signup layout with scroll support for smaller windows
        outer_frame = tk.Frame(self.root, bg=self.bg_color)
        outer_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))

        canvas = tk.Canvas(outer_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner_frame = tk.Frame(canvas, bg=self.bg_color)
        window_id = canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        def update_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(window_id, width=canvas.winfo_width())

        def on_mousewheel(event):
            if getattr(event, 'delta', None) is not None:
                scroll_amount = int(-1 * (event.delta / 120))
                if scroll_amount == 0:
                    scroll_amount = -1 if event.delta > 0 else 1
                canvas.yview_scroll(scroll_amount, "units")
            elif getattr(event, 'num', None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, 'num', None) == 5:
                canvas.yview_scroll(1, "units")

        inner_frame.bind("<Configure>", update_scrollregion)
        canvas.bind("<Configure>", update_scrollregion)
        canvas.bind('<Enter>', lambda event: canvas.focus_set())
        self.root.bind_all('<MouseWheel>', on_mousewheel)
        self.root.bind_all('<Button-4>', on_mousewheel)
        self.root.bind_all('<Button-5>', on_mousewheel)

        card = self.create_split_card(left_emoji="✏️", left_title="Join New AI BANK",
                          left_subtitle="Create your account in seconds", card_width=900, card_height=760,
                          parent=inner_frame)

        tk.Label(card, text="Join New AI BANK", font=("Arial", 18, "bold"),
                fg=self.primary_color, bg="#ffffff").pack(anchor=tk.W, padx=20, pady=(0, 5))
        tk.Label(card, text="Sign up in seconds to access smart banking, loan offers, and easy money management.",
                font=("Arial", 10), fg="#6b7280", bg="#ffffff", wraplength=520, justify=tk.LEFT).pack(anchor=tk.W, padx=20, pady=(0, 15))
        
        # Username
        tk.Label(card, text="Username", font=("Arial", 11, "bold"),
                fg=self.text_color, bg="#ffffff").pack(anchor=tk.W, padx=20, pady=(5, 5))
        username_entry = tk.Entry(card, font=("Arial", 11), width=32, bd=0, relief=tk.FLAT,
                                  bg="#f8fafc", highlightthickness=1, highlightbackground="#d1d5db",
                                  highlightcolor=self.primary_color)
        username_entry.pack(padx=20, pady=3, ipady=4)
        
        # Password
        tk.Label(card, text="Password", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(12, 4))
        password_frame = tk.Frame(card, bg=self.card_bg)
        password_frame.pack(padx=20, pady=2, fill=tk.X)
        password_entry = tk.Entry(password_frame, font=("Arial", 11), width=15, show="*")
        password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        password_visible = tk.BooleanVar(value=False)
        def toggle_password():
            visible = not password_visible.get()
            password_visible.set(visible)
            password_entry.config(show="" if visible else "*")
        password_toggle = tk.Button(password_frame, text="👁️", command=toggle_password,
                                    font=("Arial", 10), bg="#9ca3af", fg="white",
                                    padx=8, pady=2, relief=tk.FLAT, cursor="hand2")
        password_toggle.pack(side=tk.LEFT, padx=(8, 0), ipady=2)
        
        # Confirm Password
        tk.Label(card, text="Confirm Password", font=("Arial", 10, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 3))
        confirm_password_frame = tk.Frame(card, bg=self.card_bg)
        confirm_password_frame.pack(padx=20, pady=2, fill=tk.X)
        confirm_password_entry = tk.Entry(confirm_password_frame, font=("Arial", 10), width=15, show="*")
        confirm_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        confirm_password_visible = tk.BooleanVar(value=False)
        def toggle_confirm_password():
            visible = not confirm_password_visible.get()
            confirm_password_visible.set(visible)
            confirm_password_entry.config(show="" if visible else "*")
        confirm_password_toggle = tk.Button(confirm_password_frame, text="👁️", command=toggle_confirm_password,
                                            font=("Arial", 10), bg="#9ca3af", fg="white",
                                            padx=8, pady=2, relief=tk.FLAT, cursor="hand2")
        confirm_password_toggle.pack(side=tk.LEFT, padx=(8, 0), ipady=2)
        
        # Age
        tk.Label(card, text="Age", font=("Arial", 10, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 3))
        age_var = tk.StringVar(value="Select Age")
        age_options = [str(age) for age in range(10, 101)]
        age_combobox = ttk.Combobox(card, textvariable=age_var, values=age_options,
                                    font=("Arial", 10), width=22, state="normal")
        age_combobox.pack(padx=20, pady=3)
        age_combobox.configure(height=5)
        age_combobox.set("Select Age")
        age_combobox.bind("<<ComboboxSelected>>", lambda event: on_age_change())
        age_warning_label = tk.Label(card, text="", font=("Arial", 10), fg="#b91c1c", bg="#ffffff")
        age_warning_label.pack(anchor=tk.W, padx=20, pady=(0, 5))

        tk.Label(card, text="Account Type", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 5))
        account_type_var = tk.StringVar(value="Select Account Type")
        account_type_options = ["Current", "Savings"]
        account_type_menu = tk.OptionMenu(card, account_type_var, *account_type_options)
        account_type_menu.config(font=("Arial", 10), width=24, bg="#f8fafc", fg="#000000",
                                 relief=tk.FLAT, activebackground="#e2e8f0", highlightthickness=1,
                                 highlightbackground="#d1d5db")
        account_type_menu.pack(padx=20, pady=3)

        account_type_warning = tk.Label(card, text="", font=("Arial", 10), fg="#b91c1c", bg="#ffffff")
        account_type_warning.pack(anchor=tk.W, padx=20, pady=(0, 5))

        tk.Label(card, text="Company", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 5))
        company_var = tk.StringVar(value="Select Company")
        company_options = ["Accenture", "Infoysis", "IBM", "Wipro", "PWC", "Delotite"]
        company_menu = tk.OptionMenu(card, company_var, *company_options)
        company_menu.config(font=("Arial", 10), width=24, bg="#f8fafc", fg="#000000",
                           relief=tk.FLAT, activebackground="#e2e8f0", highlightthickness=1,
                           highlightbackground="#d1d5db")
        company_menu.pack(padx=20, pady=3)
        company_menu.config(state=tk.DISABLED)
        company_status_label = tk.Label(card, text="", font=("Arial", 10), fg="#1d4ed8", bg="#ffffff")
        company_status_label.pack(anchor=tk.W, padx=20, pady=(0, 5))

        signup_btn = None

        def update_signup_button_state():
            age_value = None
            try:
                age_value = int(age_var.get())
            except ValueError:
                pass
            account_type = account_type_var.get()
            company_selected = company_var.get() if account_type == "Savings" else "Selected"

            valid_age = age_value is not None and age_value >= 18
            valid_account = account_type in account_type_options
            valid_company = account_type != "Savings" or company_selected in company_options

            if signup_btn is not None:
                signup_btn.config(state=tk.NORMAL if valid_age and valid_account and valid_company else tk.DISABLED)

        def on_age_change(*args):
            selected_age = age_var.get()
            try:
                age_value = int(selected_age)
            except ValueError:
                age_value = None

            if age_value is None:
                age_warning_label.config(text="Please select your age")
            elif age_value < 18:
                age_warning_label.config(text="Under 18 years, account couldn't be created")
            else:
                age_warning_label.config(text="")

            update_signup_button_state()

        def on_account_type_change(*args):
            account_type = account_type_var.get()
            if account_type == "Current":
                account_type_warning.config(text="Please deposit 500 to proceed account creation")
                company_menu.config(state=tk.DISABLED)
                company_status_label.config(text="Company selection is optional for Current accounts")
            elif account_type == "Savings":
                account_type_warning.config(text="")
                company_menu.config(state=tk.NORMAL)
                company_status_label.config(text="Select a company for Savings account")
            else:
                account_type_warning.config(text="")
                company_menu.config(state=tk.DISABLED)
                company_status_label.config(text="")

            update_signup_button_state()

        def on_company_change(*args):
            update_signup_button_state()

        # Phone Number
        tk.Label(card, text="Phone Number (10 digits)", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        phone_entry = tk.Entry(card, font=("Arial", 11), width=40)
        phone_entry.pack(padx=20, pady=5)
        
        # Buttons frame
        btn_frame = tk.Frame(card, bg=self.card_bg)
        btn_frame.pack(pady=30)
        
        def signup_action():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            confirm_password = confirm_password_entry.get().strip()
            phone_number = phone_entry.get().strip()
            
            if not username or not password or not phone_number or age_var.get() == "Select Age" or account_type_var.get() == "Select Account Type":
                messagebox.showerror("Error", "Please fill all required fields")
                return
            
            if age_var.get() == "Select Age":
                messagebox.showerror("Error", "Please select your age")
                return

            age_value = int(age_var.get()) if age_var.get().isdigit() else None
            if age_value is None or age_value < 18:
                messagebox.showerror("Error", "Under 18 years, account couldn't be created")
                return

            if account_type_var.get() == "Select Account Type":
                messagebox.showerror("Error", "Please select an account type")
                return

            if account_type_var.get() == "Savings" and company_var.get() == "Select Company":
                messagebox.showerror("Error", "Please select a company for savings accounts")
                return

            if account_type_var.get() == "Current":
                messagebox.showinfo("Deposit Required", "Please deposit 500 to proceed account creation.")

            if password != confirm_password:
                messagebox.showerror("Error", "Passwords do not match")
                return
            
            if len(password) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters long")
                return
            
            # Validate phone number
            is_valid, result = self.db.validate_phone_number(phone_number)
            if not is_valid:
                messagebox.showerror("Error", result)
                return
            
            # Check if phone already exists
            if self.db.phone_number_exists(result):
                messagebox.showerror("Error", "This phone number is already registered with another account")
                return
            
            # Check if username already exists
            if self.db.user_exists(username):
                messagebox.showerror("Error", "This username is already taken. Please choose a different username")
                return
            
            # Register the user
            success, account_number = self.db.register_user(username, password, result)
            if success:
                messagebox.showinfo("Success", f"Account created successfully!\n\nUsername: {username}\nAccount Number: {account_number}\nPhone: {result}\nInitial Balance: $0.00\n\nYou can now login with your credentials.")
                self.show_main_page()
            else:
                messagebox.showerror("Error", account_number if isinstance(account_number, str) else "Registration failed")
        
        signup_btn = tk.Button(btn_frame, text="Create Account", command=signup_action,
                              font=("Arial", 12, "bold"), bg="#16a34a",
                              fg="white", padx=40, pady=10, relief=tk.FLAT, state=tk.DISABLED)
        signup_btn.pack(side=tk.LEFT, padx=10)
        update_signup_button_state()
        age_var.trace_add('write', on_age_change)
        account_type_var.trace_add('write', on_account_type_change)
        company_var.trace_add('write', on_company_change)
        
        back_btn = tk.Button(btn_frame, text="Back", command=self.show_main_page,
                            font=("Arial", 12, "bold"), bg="#9ca3af",
                            fg="white", padx=40, pady=10, relief=tk.FLAT)
        back_btn.pack(side=tk.LEFT, padx=10)
    
    def show_deposit_page(self):
        """Show deposit page"""
        self.clear_window()
        self.create_header("Deposit Money")
        form_container = tk.Frame(self.root, bg=self.bg_color)
        form_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=30)

        # Centered card
        card = tk.Frame(form_container, bg="#ffffff", bd=0, relief=tk.FLAT,
                highlightbackground="#e6edf8", highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER, width=760, height=420)

        # Inner split: illustration (left) + form (right)
        inner = tk.Frame(card, bg="#ffffff")
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        left = tk.Frame(inner, bg="#eef6ff", width=220)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        tk.Label(left, text="💰", font=("Arial", 48), bg="#eef6ff", fg="#0b5ed7").pack(pady=(30, 5))
        tk.Label(left, text="Fast & Secure",
             font=("Arial", 12, "bold"), fg="#0b5ed7", bg="#eef6ff").pack()
        tk.Label(left, text="Trusted deposits with instant confirmation",
             font=("Arial", 9), fg="#475569", bg="#eef6ff", wraplength=180, justify=tk.CENTER).pack(padx=10, pady=(8, 0))

        # Form area
        form = tk.Frame(inner, bg="#ffffff")
        form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 6))

        tk.Label(form, text="Deposit Funds", font=("Arial", 18, "bold"),
            fg=self.primary_color, bg="#ffffff").grid(row=0, column=0, sticky="w")
        tk.Label(form, text="Add money to your account quickly and securely.",
            font=("Arial", 10), fg="#6b7280", bg="#ffffff", wraplength=420, justify=tk.LEFT).grid(row=1, column=0, sticky="w", pady=(4, 12))

        # Username
        tk.Label(form, text="Username", font=("Arial", 11, "bold"), fg=self.text_color, bg="#ffffff").grid(row=2, column=0, sticky="w", pady=(6, 2))
        username_entry = tk.Entry(form, font=("Arial", 11), width=36, bd=0, relief=tk.FLAT,
                      bg="#f8fafc", highlightthickness=1, highlightbackground="#d1d5db",
                      highlightcolor=self.primary_color)
        username_entry.grid(row=3, column=0, sticky="w", pady=(0, 6))

        # Password
        tk.Label(form, text="Password", font=("Arial", 11, "bold"), fg=self.text_color, bg="#ffffff").grid(row=4, column=0, sticky="w", pady=(6, 2))
        password_entry = tk.Entry(form, font=("Arial", 11), width=36, show="*", bd=0, relief=tk.FLAT,
                       bg="#f8fafc")
        password_entry.grid(row=5, column=0, sticky="w", pady=(0, 6))

        # Phone Number
        tk.Label(form, text="Phone Number", font=("Arial", 11, "bold"), fg=self.text_color, bg="#ffffff").grid(row=6, column=0, sticky="w", pady=(6, 2))
        phone_entry = tk.Entry(form, font=("Arial", 11), width=36, bd=0, relief=tk.FLAT, bg="#f8fafc")
        phone_entry.grid(row=7, column=0, sticky="w", pady=(0, 6))

        # Amount
        tk.Label(form, text="Deposit Amount ($)", font=("Arial", 11, "bold"), fg=self.text_color, bg="#ffffff").grid(row=8, column=0, sticky="w", pady=(6, 2))
        amount_entry = tk.Entry(form, font=("Arial", 14), width=20, bd=0, relief=tk.FLAT, bg="#f8fafc")
        amount_entry.grid(row=9, column=0, sticky="w", pady=(0, 8))

        tk.Label(form, text="Tip: Minimum deposit $1.00. Transactions are instant.",
             font=("Arial", 9), fg="#6b7280", bg="#ffffff").grid(row=10, column=0, sticky="w", pady=(0, 12))

        btn_frame = tk.Frame(form, bg="#ffffff")
        btn_frame.grid(row=11, column=0, pady=(4, 0))
        
        def deposit_action():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            phone_number = phone_entry.get().strip()
            amount_str = amount_entry.get().strip()
            
            if not username or not password or not amount_str:
                messagebox.showerror("Error", "Please fill all required fields")
                return
            
            try:
                amount = float(amount_str)
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid amount")
                return
            
            if not self.db.user_exists(username):
                # New user registration
                if phone_number:
                    # Validate phone number
                    is_valid, result = self.db.validate_phone_number(phone_number)
                    if not is_valid:
                        messagebox.showerror("Error", result)
                        return
                    
                    # Check if phone already exists
                    if self.db.phone_number_exists(result):
                        messagebox.showerror("Error", "This phone number is already registered with another account")
                        return
                    
                    success, account_number = self.db.register_user(username, password, result)
                    if success:
                        messagebox.showinfo("Success", f"Account created!\nUsername: {username}\nAccount Number: {account_number}\nPhone: {result}\nInitial Balance: $0.00")
                        success, message = self.db.deposit(username, amount)
                        messagebox.showinfo("Success", message)
                        if self.current_user == username:
                            self.show_dashboard()
                        else:
                            self.show_main_page()
                    else:
                        messagebox.showerror("Error", account_number if isinstance(account_number, str) else "Registration failed")
                else:
                    messagebox.showerror("Error", "Phone number is required for new users")
            else:
                # Existing user
                if not self.db.validate_user(username, password):
                    messagebox.showerror("Error", "Invalid username or password")
                    return
                
                success, message = self.db.deposit(username, amount)
                if success:
                    self.show_big_popup("Deposit Successful", "Funds have been added to your account:", f"${amount:.2f}")
                    if self.current_user == username:
                        self.show_dashboard()
                    else:
                        self.show_main_page()
                else:
                    messagebox.showerror("Error", message)
        
        deposit_btn = tk.Button(btn_frame, text="Deposit", command=deposit_action,
                               font=("Arial", 12, "bold"), bg=self.success_color,
                               fg="white", padx=40, pady=10, relief=tk.FLAT)
        deposit_btn.pack(side=tk.LEFT, padx=10)
        
        back_btn = tk.Button(btn_frame, text="Back", command=self.show_main_page,
                            font=("Arial", 12, "bold"), bg="#9ca3af",
                            fg="white", padx=40, pady=10, relief=tk.FLAT)
        back_btn.pack(side=tk.LEFT, padx=10)
    
    def show_withdraw_page(self):
        """Show withdraw page"""
        self.clear_window()
        self.create_header("Withdraw Money")
        # Split card layout
        card = self.create_split_card(left_emoji="💸", left_title="Withdraw Cash",
                                      left_subtitle="Secure withdrawals and instant updates", card_height=520)

        tk.Label(card, text="Withdraw Cash", font=("Arial", 18, "bold"),
                fg=self.primary_color, bg="#ffffff").pack(anchor=tk.W, padx=20, pady=(0, 5))
        tk.Label(card, text="Withdraw funds safely and keep your account up to date with every transaction.",
                font=("Arial", 10), fg="#6b7280", bg="#ffffff", wraplength=520, justify=tk.LEFT).pack(anchor=tk.W, padx=20, pady=(0, 15))
        
        # Username
        tk.Label(card, text="Username", font=("Arial", 11, "bold"),
                fg=self.text_color, bg="#ffffff").pack(anchor=tk.W, padx=20, pady=(5, 5))
        username_entry = tk.Entry(card, font=("Arial", 11), width=40, bd=0, relief=tk.FLAT,
                                  bg="#f8fafc", highlightthickness=1, highlightbackground="#d1d5db",
                                  highlightcolor=self.primary_color)
        username_entry.pack(padx=20, pady=5, ipady=8)
        
        # Password
        tk.Label(card, text="Password", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        password_entry = tk.Entry(card, font=("Arial", 11), width=40, show="*")
        password_entry.pack(padx=20, pady=5)
        
        # Phone Number
        tk.Label(card, text="Phone Number", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        phone_entry = tk.Entry(card, font=("Arial", 11), width=40)
        phone_entry.pack(padx=20, pady=5)
        
        # Amount
        tk.Label(card, text="Withdraw Amount ($)", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        amount_entry = tk.Entry(card, font=("Arial", 11), width=40)
        amount_entry.pack(padx=20, pady=5)
        
        btn_frame = tk.Frame(card, bg=self.card_bg)
        btn_frame.pack(pady=30)
        
        def withdraw_action():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            phone_number = phone_entry.get().strip()
            amount_str = amount_entry.get().strip()
            
            if not username or not password or not amount_str:
                messagebox.showerror("Error", "Please fill all required fields")
                return
            
            try:
                amount = float(amount_str)
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid amount")
                return
            
            if not self.db.user_exists(username):
                # New user registration
                if phone_number:
                    # Validate phone number
                    is_valid, result = self.db.validate_phone_number(phone_number)
                    if not is_valid:
                        messagebox.showerror("Error", result)
                        return
                    
                    # Check if phone already exists
                    if self.db.phone_number_exists(result):
                        messagebox.showerror("Error", "This phone number is already registered with another account")
                        return
                    
                    success, account_number = self.db.register_user(username, password, result)
                    if success:
                        messagebox.showinfo("Success", f"Account created!\nUsername: {username}\nAccount Number: {account_number}\nPhone: {result}\nInitial Balance: $0.00")
                        success, message = self.db.withdraw(username, amount)
                        if success:
                            messagebox.showinfo("Success", message)
                            if self.current_user == username:
                                self.show_dashboard()
                            else:
                                self.show_main_page()
                        else:
                            messagebox.showerror("Error", message)
                    else:
                        messagebox.showerror("Error", account_number if isinstance(account_number, str) else "Registration failed")
                else:
                    messagebox.showerror("Error", "Phone number is required for new users")
            else:
                # Validate user
                if not self.db.validate_user(username, password):
                    messagebox.showerror("Error", "Invalid username or password")
                    return
                
                success, message = self.db.withdraw(username, amount)
                if success:
                    self.show_big_popup("Withdrawal Successful", "The following amount has been withdrawn:", f"${amount:.2f}")
                    if self.current_user == username:
                        self.show_dashboard()
                    else:
                        self.show_main_page()
                else:
                    messagebox.showerror("Error", message)
        
        withdraw_btn = tk.Button(btn_frame, text="Withdraw", command=withdraw_action,
                                font=("Arial", 12, "bold"), bg=self.danger_color,
                                fg="white", padx=40, pady=10, relief=tk.FLAT)
        withdraw_btn.pack(side=tk.LEFT, padx=10)
        
        back_btn = tk.Button(btn_frame, text="Back", command=self.show_main_page,
                            font=("Arial", 12, "bold"), bg="#9ca3af",
                            fg="white", padx=40, pady=10, relief=tk.FLAT)
        back_btn.pack(side=tk.LEFT, padx=10)
    
    def show_balance_page(self):
        """Show balance check page"""
        self.clear_window()
        self.create_header("Check Balance")
        
        # Split card layout
        card = self.create_split_card(left_emoji="💳", left_title="Your Balance",
                                      left_subtitle="Check balance & transaction history")

        tk.Label(card, text="Your Balance", font=("Arial", 18, "bold"),
                fg=self.primary_color, bg="#ffffff").pack(anchor=tk.W, padx=20, pady=(0, 5))
        tk.Label(card, text="Check your current balance and transaction history in one secure place.",
                font=("Arial", 10), fg="#6b7280", bg="#ffffff", wraplength=520, justify=tk.LEFT).pack(anchor=tk.W, padx=20, pady=(0, 15))
        
        # Username
        tk.Label(card, text="Username", font=("Arial", 11, "bold"),
                fg=self.text_color, bg="#ffffff").pack(anchor=tk.W, padx=20, pady=(5, 5))
        username_entry = tk.Entry(card, font=("Arial", 11), width=40, bd=0, relief=tk.FLAT,
                                  bg="#f8fafc", highlightthickness=1, highlightbackground="#d1d5db",
                                  highlightcolor=self.primary_color)
        username_entry.pack(padx=20, pady=5, ipady=8)
        
        # Password
        tk.Label(card, text="Password", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(15, 5))
        password_entry = tk.Entry(card, font=("Arial", 11), width=40, show="*")
        password_entry.pack(padx=20, pady=5)
        
        btn_frame = tk.Frame(card, bg=self.card_bg)
        btn_frame.pack(pady=30)
        
        def check_balance_action():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            
            if not username or not password:
                messagebox.showerror("Error", "Please enter username and password")
                return
            
            if self.db.validate_user(username, password):
                balance = self.db.get_balance(username)
                self.show_big_popup("Current Balance", "Your available account balance is:", f"${balance:.2f}")
                self.show_transaction_history(username)
            else:
                messagebox.showerror("Error", "Invalid username or password")
        
        check_btn = tk.Button(btn_frame, text="Check Balance", command=check_balance_action,
                             font=("Arial", 12, "bold"), bg="#8b5cf6",
                             fg="white", padx=40, pady=10, relief=tk.FLAT)
        check_btn.pack(side=tk.LEFT, padx=10)
        
        back_btn = tk.Button(btn_frame, text="Back", command=self.show_main_page,
                            font=("Arial", 12, "bold"), bg="#9ca3af",
                            fg="white", padx=40, pady=10, relief=tk.FLAT)
        back_btn.pack(side=tk.LEFT, padx=10)
    
    def show_search_page(self):
        """Show search user page"""
        self.clear_window()
        self.create_header("Search User")
        
        # Split card layout (form_container will be the inner form frame)
        form_container = self.create_split_card(left_emoji="🔍", left_title="Search Users",
                                               left_subtitle="Find users quickly and securely", card_height=520)
        
        # Search section
        search_frame = tk.Frame(form_container, bg=self.card_bg, relief=tk.FLAT)
        search_frame.pack(pady=12, padx=12, fill=tk.X)
        
        tk.Label(search_frame, text="Username", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(20, 5))
        username_entry = tk.Entry(search_frame, font=("Arial", 11), width=40)
        username_entry.pack(padx=20, pady=5)
        
        # Password display and toggle
        password_display_frame = tk.Frame(form_container, bg=self.bg_color)
        password_display_frame.pack(pady=(6, 8), fill=tk.X)
        tk.Label(password_display_frame, text="Password:", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.bg_color).pack(side=tk.LEFT, padx=(50, 0))

        password_value_label = tk.Label(password_display_frame, text="******", font=("Arial", 11),
                                        fg=self.primary_color, bg=self.bg_color)
        password_value_label.pack(side=tk.LEFT, padx=(10, 0))

        password_visible = tk.BooleanVar(value=False)
        current_password = [None]

        def update_password_display():
            if current_password[0] is None:
                password_value_label.config(text="******")
                toggle_password_btn.config(state=tk.DISABLED, text="Show")
                return
            toggle_password_btn.config(state=tk.NORMAL)
            if password_visible.get():
                password_value_label.config(text=current_password[0] or "N/A")
                toggle_password_btn.config(text="Hide")
            else:
                password_value_label.config(text="******")
                toggle_password_btn.config(text="Show")

        def toggle_password_visibility():
            if current_password[0] is None:
                return
            password_visible.set(not password_visible.get())
            update_password_display()

        toggle_password_btn = tk.Button(password_display_frame, text="Show",
                                        command=toggle_password_visibility,
                                        font=("Arial", 10), bg="#8b5cf6", fg="white",
                                        padx=10, pady=5, relief=tk.FLAT, cursor="hand2",
                                        state=tk.DISABLED)
        toggle_password_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Action buttons row
        action_btn_frame = tk.Frame(form_container, bg=self.bg_color)
        action_btn_frame.pack(pady=(4, 12), padx=12, fill=tk.X)

        search_btn = tk.Button(action_btn_frame, text="Search", command=lambda: search_action(),
                              font=("Arial", 12, "bold"), bg=self.primary_color,
                              fg="white", padx=30, pady=10, relief=tk.FLAT)
        search_btn.pack(side=tk.LEFT, padx=6)
        
        all_btn = tk.Button(action_btn_frame, text="View All Users", command=lambda: view_all_action(),
                           font=("Arial", 12, "bold"), bg="#06b6d4",
                           fg="white", padx=30, pady=10, relief=tk.FLAT)
        all_btn.pack(side=tk.LEFT, padx=6)

        delete_btn = tk.Button(action_btn_frame, text="Delete User", command=lambda: delete_action(),
                               font=("Arial", 12, "bold"), bg="#dc2626",
                               fg="white", padx=30, pady=10, relief=tk.FLAT,
                               state=tk.DISABLED)
        delete_btn.pack(side=tk.LEFT, padx=6)

        back_btn = tk.Button(action_btn_frame, text="Back", command=self.show_main_page,
                            font=("Arial", 12, "bold"), bg="#9ca3af",
                            fg="white", padx=30, pady=10, relief=tk.FLAT)
        back_btn.pack(side=tk.LEFT, padx=6)

        # Result display area as a selectable table
        result_frame = tk.Frame(form_container, bg=self.card_bg, relief=tk.FLAT)
        result_frame.pack(pady=8, padx=12, fill=tk.BOTH, expand=True)

        columns = ("Username", "Account", "Phone", "Balance", "Created")
        # Use a smaller height so action buttons remain visible inside the card
        tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=6)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor=tk.W, width=140)
        tree.column("Created", width=180)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=8)

        scrollbar = tk.Scrollbar(result_frame, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.config(yscrollcommand=scrollbar.set)

        selected_user_label = tk.Label(form_container, text="Selected user: None",
                                       font=("Arial", 10), fg=self.text_color, bg=self.bg_color)
        selected_user_label.pack(anchor=tk.W, padx=12, pady=(6, 4))

        bottom_btn_frame = tk.Frame(form_container, bg=self.bg_color)
        bottom_btn_frame.pack(fill=tk.X, padx=12, pady=(6, 12))

        back_bottom_btn = tk.Button(bottom_btn_frame, text="Back to Home", command=self.show_main_page,
                                    font=("Arial", 12, "bold"), bg="#9ca3af",
                                    fg="white", padx=25, pady=10, relief=tk.FLAT)
        back_bottom_btn.pack(side=tk.RIGHT, padx=12)

        def update_password_display(item_id=None):
            if item_id is None or item_id not in user_passwords:
                password_value_label.config(text="******")
                toggle_password_btn.config(state=tk.DISABLED, text="Show")
                selected_user_label.config(text="Selected user: None")
                return
            toggle_password_btn.config(state=tk.NORMAL)
            selected_user_label.config(text=f"Selected user: {tree.item(item_id, 'values')[0]}")
            if password_visible.get():
                password_value_label.config(text=user_passwords[item_id] or "N/A")
                toggle_password_btn.config(text="Hide")
            else:
                password_value_label.config(text="******")
                toggle_password_btn.config(text="Show")

        def toggle_password_visibility():
            item_id = tree.focus()
            if not item_id or item_id not in user_passwords:
                return
            password_visible.set(not password_visible.get())
            update_password_display(item_id)

        toggle_password_btn.config(command=toggle_password_visibility)

        user_passwords = {}

        def on_user_select(event):
            selected_item = tree.focus()
            password_visible.set(False)
            update_password_display(selected_item)
            if selected_item and selected_item in user_passwords:
                delete_btn.config(state=tk.NORMAL)
            else:
                delete_btn.config(state=tk.DISABLED)

        tree.bind('<<TreeviewSelect>>', on_user_select)
        
        def ask_delete_credentials():
            dialog = tk.Toplevel(self.root)
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.title("Delete User Confirmation")
            dialog.geometry("360x180")
            dialog.resizable(False, False)

            tk.Label(dialog, text="Confirm admin credentials", font=("Arial", 11, "bold"))
            tk.Label(dialog, text="Username:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(15, 5))
            username_entry = tk.Entry(dialog, font=("Arial", 10), width=30)
            username_entry.pack(padx=20)

            tk.Label(dialog, text="Password:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(10, 5))
            password_entry = tk.Entry(dialog, font=("Arial", 10), width=30, show="*")
            password_entry.pack(padx=20)

            result = {"username": None, "password": None, "confirmed": False}

            def on_confirm():
                result["username"] = username_entry.get().strip()
                result["password"] = password_entry.get().strip()
                result["confirmed"] = True
                dialog.destroy()

            def on_cancel():
                dialog.destroy()

            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=15)
            tk.Button(btn_frame, text="Confirm", command=on_confirm,
                      font=("Arial", 10, "bold"), bg="#16a34a", fg="white",
                      padx=20, pady=6, relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
            tk.Button(btn_frame, text="Cancel", command=on_cancel,
                      font=("Arial", 10, "bold"), bg="#9ca3af", fg="white",
                      padx=20, pady=6, relief=tk.FLAT).pack(side=tk.LEFT, padx=10)

            username_entry.focus_set()
            self.root.wait_window(dialog)
            return result if result["confirmed"] else None

        def delete_action():
            selected_item = tree.focus()
            if not selected_item or selected_item not in user_passwords:
                messagebox.showerror("Error", "Please select a user to delete")
                return

            selected_values = tree.item(selected_item, 'values')
            selected_username = selected_values[0]

            if self.is_delete_locked_out(selected_username):
                hours, minutes = self.get_delete_lockout_remaining(selected_username)
                message = f"Delete login attempt failed. Try after {hours} hour(s) and {minutes} minute(s)."
                messagebox.showerror("Locked Out", message)
                return

            credentials = ask_delete_credentials()
            if not credentials:
                return

            if credentials["username"] != "Surya" or credentials["password"] != "Surya@143":
                attempts, locked = self.increment_delete_attempt(selected_username)
                if locked:
                    messagebox.showerror("Error", "Login attempt failed. Try after 24 hours.")
                else:
                    remaining = 3 - attempts
                    messagebox.showerror("Error", f"Invalid confirmation credentials. {remaining} attempt(s) remaining.")
                return

            state = self.get_delete_lockout_state(selected_username)
            state["attempts"] = 0
            state["lockout_until"] = None

            confirm = messagebox.askyesno("Delete User",
                                          f"Are you sure you want to delete user '{selected_username}'?")
            if not confirm:
                return

            success, message = self.db.delete_user(selected_username)
            if success:
                messagebox.showinfo("Success", message)
                tree.delete(selected_item)
                user_passwords.pop(selected_item, None)
                password_visible.set(False)
                update_password_display(None)
                delete_btn.config(state=tk.DISABLED)
            else:
                messagebox.showerror("Error", message)

        def search_action():
            username = username_entry.get().strip()
            
            if not username:
                messagebox.showerror("Error", "Please enter username to search")
                return
            
            user = self.db.search_user(username)
            tree.delete(*tree.get_children())
            user_passwords.clear()
            password_visible.set(False)
            update_password_display(None)
            
            if user:
                user_id, account_number, uname, balance, created, stored_password = user
                phone_number = self.db.get_user_phone_number(uname) or "N/A"
                item_id = tree.insert('', 'end', values=(uname, account_number, phone_number, f"${balance:.2f}", created))
                user_passwords[item_id] = stored_password or ""
                tree.focus(item_id)
                tree.selection_set(item_id)
                update_password_display(item_id)
            else:
                messagebox.showwarning("Not Found", f"User '{username}' does not exist")
        
        def view_all_action():
            users = self.db.get_all_users()
            tree.delete(*tree.get_children())
            user_passwords.clear()
            password_visible.set(False)
            update_password_display(None)
            
            if users:
                for user in users:
                    user_id, account_number, uname, balance, created, stored_password = user
                    phone_number = self.db.get_user_phone_number(uname) or "N/A"
                    item_id = tree.insert('', 'end', values=(uname, account_number, phone_number, f"${balance:.2f}", created))
                    user_passwords[item_id] = stored_password or ""
            else:
                messagebox.showinfo("Info", "No users registered yet.")

    def show_loan_offers_page(self):
        """Show available loan offers and interest rates."""
        self.clear_window()
        self.create_header("Loan Offers")

        # Split card layout (form_container will be the inner form frame)
        form_container = self.create_split_card(left_emoji="📈", left_title="Loan Offers",
                                               left_subtitle="Competitive APRs and flexible terms", card_height=360)

        offer_banner = tk.Frame(form_container, bg="#fde68a", bd=1, relief=tk.FLAT)
        offer_banner.pack(fill=tk.X, padx=50, pady=(0, 20))
        tk.Label(offer_banner, text="Limited-time offer: Get competitive loan rates with simplified approval.",
                font=("Arial", 12, "bold"), fg="#92400e", bg="#fde68a").pack(padx=20, pady=15)

        offers = self.db.get_loan_offers()
        columns = ("Type", "Rate", "Min", "Max", "Term Options")
        tree = ttk.Treeview(form_container, columns=columns, show='headings', height=8)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor=tk.W, width=140)
        tree.pack(fill=tk.BOTH, expand=True, padx=50, pady=(0, 20))

        for offer in offers:
            periods = ", ".join(str(term) for term in offer["terms"])
            tree.insert('', 'end', values=(offer["type"], f"{offer['rate']:.2f}%", f"${offer['min_amount']:.0f}", f"${offer['max_amount']:.0f}", periods))

        btn_frame = tk.Frame(form_container, bg=self.bg_color)
        btn_frame.pack(pady=10)

        def apply_selected_offer():
            item_id = tree.focus()
            if not item_id:
                messagebox.showerror("Error", "Please select a loan offer to apply")
                return
            values = tree.item(item_id, 'values')
            if not values:
                messagebox.showerror("Error", "Unable to read selected offer")
                return
            loan_type = values[0]
            self.show_loan_application_page(loan_type)

        apply_btn = tk.Button(btn_frame, text="Apply Now", command=apply_selected_offer,
                              font=("Arial", 12, "bold"), bg="#f97316",
                              fg="white", padx=30, pady=10, relief=tk.FLAT)
        apply_btn.pack(side=tk.LEFT, padx=10)

        home_btn = tk.Button(btn_frame, text="Back", command=self.show_main_page,
                              font=("Arial", 12, "bold"), bg="#9ca3af",
                              fg="white", padx=30, pady=10, relief=tk.FLAT)
        home_btn.pack(side=tk.LEFT, padx=10)

    def show_loan_application_page(self, loan_type=None):
        """Show loan application page for the selected loan type."""
        self.clear_window()
        self.create_header("Apply for Loan")

        form_container = tk.Frame(self.root, bg=self.bg_color)
        form_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        card = tk.Frame(form_container, bg=self.card_bg, relief=tk.FLAT)
        card.pack(pady=20, padx=50)

        tk.Label(card, text="Loan Application", font=("Arial", 16, "bold"),
                fg=self.primary_color, bg=self.card_bg).pack(pady=(20, 10))

        tk.Label(card, text="Username", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 5))
        username_entry = tk.Entry(card, font=("Arial", 11), width=40)
        username_entry.pack(padx=20, pady=5)

        tk.Label(card, text="Password", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 5))
        password_entry = tk.Entry(card, font=("Arial", 11), width=40, show="*")
        password_entry.pack(padx=20, pady=5)

        tk.Label(card, text="Loan Type", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 5))
        loan_types = [offer["type"] for offer in self.db.get_loan_offers()]
        loan_type_var = tk.StringVar(value=loan_type if loan_type in loan_types else loan_types[0])
        loan_menu = ttk.Combobox(card, textvariable=loan_type_var, values=loan_types, state="readonly", width=37)
        loan_menu.pack(padx=20, pady=5)

        tk.Label(card, text="Loan Amount ($)", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 5))
        amount_entry = tk.Entry(card, font=("Arial", 11), width=40)
        amount_entry.pack(padx=20, pady=5)

        tk.Label(card, text="Term (months)", font=("Arial", 11, "bold"),
                fg=self.text_color, bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 5))
        term_var = tk.StringVar(value="12")
        term_menu = ttk.Combobox(card, textvariable=term_var, state="readonly", width=37)
        term_menu.pack(padx=20, pady=5)

        def update_terms(event=None):
            selected_type = loan_type_var.get()
            selected_offer = next((offer for offer in self.db.get_loan_offers() if offer["type"] == selected_type), None)
            if selected_offer:
                term_menu['values'] = [str(term) for term in selected_offer["terms"]]
                term_var.set(str(selected_offer["terms"] [0]))

        loan_menu.bind('<<ComboboxSelected>>', update_terms)
        update_terms()

        details_label = tk.Label(card, text="", font=("Arial", 10), fg="#4b5563", bg=self.card_bg, wraplength=560, justify=tk.LEFT)
        details_label.pack(padx=20, pady=(10, 5))

        def update_details(event=None):
            selected_type = loan_type_var.get()
            selected_offer = next((offer for offer in self.db.get_loan_offers() if offer["type"] == selected_type), None)
            if selected_offer:
                details_label.config(text=(f"Offer: {selected_type} at {selected_offer['rate']:.2f}% APR. "
                                           f"Minimum ${selected_offer['min_amount']:.0f}, maximum ${selected_offer['max_amount']:.0f}. "
                                           f"Available terms: {', '.join(str(term) for term in selected_offer['terms'])} months."))

        loan_menu.bind('<<ComboboxSelected>>', update_details)
        update_details()

        btn_frame = tk.Frame(card, bg=self.card_bg)
        btn_frame.pack(pady=20)

        def submit_loan_request():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            amount_str = amount_entry.get().strip()
            selected_term = term_var.get().strip()
            selected_type = loan_type_var.get().strip()

            if not username or not password or not amount_str or not selected_term:
                messagebox.showerror("Error", "Please fill all required fields")
                return
            try:
                principal = float(amount_str)
                term_months = int(selected_term)
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numeric values for amount and term")
                return

            if not self.db.validate_user(username, password):
                messagebox.showerror("Error", "Invalid username or password")
                return

            success, message = self.db.apply_loan(username, selected_type, principal, term_months)
            if success:
                messagebox.showinfo("Success", message)
                self.current_user = username
                self.show_dashboard()
            else:
                messagebox.showerror("Error", message)

        apply_btn = tk.Button(btn_frame, text="Apply For Loan", command=submit_loan_request,
                               font=("Arial", 12, "bold"), bg="#f97316",
                               fg="white", padx=40, pady=10, relief=tk.FLAT)
        apply_btn.pack(side=tk.LEFT, padx=10)

        back_btn = tk.Button(btn_frame, text="Back", command=self.show_loan_offers_page,
                              font=("Arial", 12, "bold"), bg="#9ca3af",
                              fg="white", padx=40, pady=10, relief=tk.FLAT)
        back_btn.pack(side=tk.LEFT, padx=10)

    def show_loan_history_page(self):
        """Show the logged-in user's loan history."""
        self.clear_window()
        self.create_header("Loan History")

        form_container = tk.Frame(self.root, bg=self.bg_color)
        form_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=30)

        if not self.current_user:
            tk.Label(form_container, text="Please login to view your loan history.", font=("Arial", 12), fg=self.text_color, bg=self.bg_color).pack(pady=20)
            back_btn = tk.Button(form_container, text="Back", command=self.show_dashboard,
                                  font=("Arial", 12, "bold"), bg="#9ca3af",
                                  fg="white", padx=40, pady=10, relief=tk.FLAT)
            back_btn.pack(pady=10)
            return

        history = self.db.get_loan_history(self.current_user)
        columns = ("Type", "Amount", "Rate", "Term", "Monthly", "Total", "Status", "Applied")
        tree = ttk.Treeview(form_container, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor=tk.W, width=110)
        tree.pack(fill=tk.BOTH, expand=True, padx=50, pady=20)

        if history:
            for loan in history:
                loan_type, principal, rate, term, monthly, total, status, applied_at = loan
                tree.insert('', 'end', values=(loan_type, f"${principal:.2f}", f"{rate:.2f}%", f"{term}m", f"${monthly:.2f}", f"${total:.2f}", status, applied_at))
        else:
            tk.Label(form_container, text="No loans have been applied for yet.", font=("Arial", 12), fg="#4b5563", bg=self.bg_color).pack(pady=20)

        btn_frame = tk.Frame(form_container, bg=self.bg_color)
        btn_frame.pack(pady=10)
        back_btn = tk.Button(btn_frame, text="Back to Dashboard", command=self.show_dashboard,
                              font=("Arial", 12, "bold"), bg="#9ca3af",
                              fg="white", padx=40, pady=10, relief=tk.FLAT)
        back_btn.pack()

    def show_transaction_history(self, username):
        """Show transaction history in a new window"""
        history_win = tk.Toplevel(self.root)
        history_win.title(f"Transaction History - {username}")
        history_win.geometry("600x400")
        history_win.configure(bg=self.bg_color)

        header = tk.Label(history_win, text="Transaction History",
                          font=("Arial", 14, "bold"), bg=self.primary_color, fg="white")
        header.pack(fill=tk.X, pady=10)

        columns = ("Type", "Amount", "Balance", "Date")
        tree = ttk.Treeview(history_win, columns=columns, show='headings', height=15)
        tree.column("Type", anchor=tk.W, width=120)
        tree.column("Amount", anchor=tk.CENTER, width=100)
        tree.column("Balance", anchor=tk.CENTER, width=100)
        tree.column("Date", anchor=tk.W, width=220)

        for col in columns:
            tree.heading(col, text=col)

        scrollbar = tk.Scrollbar(history_win, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        transactions = self.db.get_transaction_history(username)
        for idx, txn in enumerate(transactions):
            # txn: (id, user_id, transaction_type, amount, balance_after, timestamp)
            tree.insert('', 'end', iid=idx,
                        values=(txn[2], f"${txn[3]:.2f}", f"${txn[4]:.2f}", txn[5]))

        # Export CSV button
        def export_csv():
            if not transactions:
                messagebox.showinfo("No transactions", "No transactions to export")
                return
            filename = filedialog.asksaveasfilename(defaultextension=".csv",
                                                    filetypes=[("CSV files", "*.csv")],
                                                    initialfile=f"{username}_transactions.csv")
            if not filename:
                return
            try:
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Transaction ID", "User ID", "Type", "Amount", "Balance", "Date"])
                    for txn in transactions:
                        # txn: (id, user_id, transaction_type, amount, balance_after, timestamp)
                        writer.writerow([txn[0], txn[1], txn[2], f"{txn[3]:.2f}", f"{txn[4]:.2f}", txn[5]])
                messagebox.showinfo("Export Successful", f"Transactions exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Export Failed", f"Could not export CSV: {str(e)}")

        export_btn = tk.Button(history_win, text="Download CSV", command=export_csv,
                               font=("Arial", 11, "bold"), bg=self.primary_color, fg="white",
                               padx=12, pady=8, relief=tk.FLAT)
        export_btn.pack(pady=(0, 12))

    def show_dashboard(self):
        """Show user dashboard after login"""
        self.clear_window()
        self.create_header()
        
        main_container = tk.Frame(self.root, bg=self.bg_color)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=40)
        
        balance = self.db.get_balance(self.current_user)
        account_number = self.db.get_account_number(self.current_user)
        
        # Account Info Card
        info_card = tk.Frame(main_container, bg=self.card_bg, relief=tk.FLAT, bd=1)
        info_card.pack(pady=10, fill=tk.X)
        
        tk.Label(info_card, text=f"Account Number: {account_number}", font=("Arial", 10),
                fg="#6b7280", bg=self.card_bg).pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        # Balance Card
        balance_card = tk.Frame(main_container, bg="#10b981", relief=tk.FLAT)
        balance_card.pack(pady=20, fill=tk.X)
        
        tk.Label(balance_card, text="Current Balance", font=("Arial", 12),
                fg="#d1fae5", bg="#10b981").pack(anchor=tk.W, padx=20, pady=(10, 0))
        self.balance_amount_label = tk.Label(balance_card, text=f"${balance:.2f}", font=("Arial", 28, "bold"),
                fg="white", bg="#10b981")
        self.balance_amount_label.pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Actions
        tk.Label(main_container, text="Quick Actions", font=("Arial", 14, "bold"),
                fg=self.text_color, bg=self.bg_color).pack(pady=(20, 10))
        
        actions_frame = tk.Frame(main_container, bg=self.bg_color)
        actions_frame.pack(pady=10)
        
        deposit_btn = tk.Button(actions_frame, text="💰 Deposit", command=self.show_deposit_page,
                               font=("Arial", 12, "bold"), bg=self.success_color,
                               fg="white", padx=30, pady=10, relief=tk.FLAT)
        deposit_btn.pack(side=tk.LEFT, padx=10)
        
        withdraw_btn = tk.Button(actions_frame, text="💸 Withdraw", command=self.show_withdraw_page,
                                font=("Arial", 12, "bold"), bg=self.danger_color,
                                fg="white", padx=30, pady=10, relief=tk.FLAT)
        withdraw_btn.pack(side=tk.LEFT, padx=10)

        balance_btn = tk.Button(actions_frame, text="💳 Check Balance", command=self.show_balance_page,
                                font=("Arial", 12, "bold"), bg="#8b5cf6",
                                fg="white", padx=30, pady=10, relief=tk.FLAT)
        balance_btn.pack(side=tk.LEFT, padx=10)

        def export_dashboard_csv():
            if not self.current_user:
                messagebox.showerror("Error", "No user logged in")
                return
            transactions = self.db.get_all_transactions(self.current_user)
            if not transactions:
                messagebox.showinfo("No transactions", "No transactions available to export")
                return
            filename = filedialog.asksaveasfilename(defaultextension=".csv",
                                                    filetypes=[("CSV files", "*.csv")],
                                                    initialfile=f"{self.current_user}_transactions.csv")
            if not filename:
                return
            try:
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Transaction ID", "User ID", "Type", "Amount", "Balance", "Date"])
                    for txn in transactions:
                        writer.writerow([txn[0], txn[1], txn[2], f"{txn[3]:.2f}", f"{txn[4]:.2f}", txn[5]])
                messagebox.showinfo("Export Successful", f"Transactions exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Export Failed", f"Could not export CSV: {str(e)}")

        export_btn = tk.Button(actions_frame, text="📥 Export Transactions", command=export_dashboard_csv,
                               font=("Arial", 12, "bold"), bg="#0ea5a4",
                               fg="white", padx=20, pady=10, relief=tk.FLAT)
        export_btn.pack(side=tk.LEFT, padx=10)

        loan_btn = tk.Button(actions_frame, text="💼 Loan Offers", command=self.show_loan_offers_page,
                              font=("Arial", 12, "bold"), bg="#f97316",
                              fg="white", padx=30, pady=10, relief=tk.FLAT)
        loan_btn.pack(side=tk.LEFT, padx=10)
        
        # Logout
        logout_btn = tk.Button(main_container, text="Logout", command=self.show_main_page,
                              font=("Arial", 12, "bold"), bg="#9ca3af",
                              fg="white", padx=30, pady=10, relief=tk.FLAT)
        logout_btn.pack(pady=20)

    def refresh_dashboard_balance(self):
        """Refresh the balance label on the dashboard."""
        if self.current_user and hasattr(self, 'balance_amount_label'):
            balance = self.db.get_balance(self.current_user)
            self.balance_amount_label.config(text=f"${balance:.2f}")


# ==================== MAIN ====================

if __name__ == "__main__":
    root = tk.Tk()
    app = BankingApp(root)
    root.mainloop()
