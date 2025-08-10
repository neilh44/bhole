# app.py - Main Flask Application
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, date
import json
import os
from typing import Dict, List, Optional

# Configure Flask to use 'template' folder instead of default 'templates'
app = Flask(__name__, template_folder='template')
app.secret_key = 'your-secret-key-here'  # Change this in production

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'YOUR_SUPABASE_URL_HERE')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'YOUR_SUPABASE_ANON_KEY_HERE')

# Initialize Supabase client (optional - works without it)
supabase = None
try:
    from supabase import create_client, Client
    if SUPABASE_URL != 'YOUR_SUPABASE_URL_HERE' and SUPABASE_KEY != 'YOUR_SUPABASE_ANON_KEY_HERE':
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Connected to Supabase successfully!")
    else:
        print("ℹ️  Using local storage mode (Supabase not configured)")
except ImportError:
    print("ℹ️  Supabase not installed - using local storage mode")
except Exception as e:
    print(f"⚠️  Could not connect to Supabase: {e}")
    print("ℹ️  Falling back to local storage mode")

class InventoryManager:
    """Handles all inventory-related operations"""
    
    def __init__(self):
        self.flavors = [
            'Vanilla', 'Chocolate', 'Strawberry', 'Mango', 
            'Kulfi', 'Butterscotch', 'Pista', 'Chocolate Chip',
            'Black Current', 'Orange', 'Coconut', 'Cassata'
        ]
        
        # Create data directory for local storage
        os.makedirs('data', exist_ok=True)
        
        # Initialize local storage files with default data
        self._init_local_storage()
    
    def test_supabase_write(self):
        """Test if we can write to Supabase"""
        if not supabase:
            return False, "Supabase not connected"
        
        try:
            # Try to insert/update a test record
            test_response = supabase.table('inventory').upsert({
                'flavor': 'TEST_FLAVOR',
                'count': 999
            }).execute()
            
            # Clean up test record
            supabase.table('inventory').delete().eq('flavor', 'TEST_FLAVOR').execute()
            
            return True, "Write test successful"
        except Exception as e:
            return False, f"Write test failed: {str(e)}"
        
    def _init_local_storage(self):
        """Initialize local JSON files with default data if they don't exist"""
        inventory_file = 'data/inventory.json'
        sales_file = 'data/sales.json'
        
        # Initialize inventory file
        if not os.path.exists(inventory_file):
            default_inventory = {flavor: 0 for flavor in self.flavors}
            self._save_to_file(inventory_file, default_inventory)
            print("📦 Initialized local inventory storage")
        
        # Initialize sales file
        if not os.path.exists(sales_file):
            self._save_to_file(sales_file, [])
            print("💰 Initialized local sales storage")
    
    def get_inventory(self) -> Dict[str, int]:
        """Get current inventory from database or fallback to local storage"""
        try:
            if supabase:
                response = supabase.table('inventory').select('*').execute()
                inventory = {}
                for item in response.data:
                    inventory[item['flavor']] = item['count']
                return inventory
            else:
                # Fallback to JSON file
                return self._load_from_file('data/inventory.json')
        except Exception as e:
            print(f"Error loading inventory: {e}")
            # Return default inventory on error
            return {flavor: 0 for flavor in self.flavors}

    def add_new_flavor(self, flavor: str) -> bool:
        """Add a new flavor to the system"""
        try:
            # Clean up the flavor name
            flavor = flavor.strip().title()
            
            if not flavor:
                return False
                
            # Check if flavor already exists
            current_inventory = self.get_inventory()
            if flavor in current_inventory:
                return False  # Flavor already exists
            
            if supabase:
                # Add to database
                supabase.table('inventory').insert({
                    'flavor': flavor,
                    'count': 0,
                    'updated_at': datetime.now().isoformat()
                }).execute()
            else:
                # Add to local storage
                current_inventory[flavor] = 0
                self._save_to_file('data/inventory.json', current_inventory)
            
            # Add to flavors list
            if flavor not in self.flavors:
                self.flavors.append(flavor)
                self.flavors.sort()  # Keep alphabetical order
            
            return True
        except Exception as e:
            print(f"Error adding new flavor: {e}")
            return False

    def get_all_flavors(self) -> List[str]:
        """Get all available flavors (including custom ones from database)"""
        try:
            if supabase:
                response = supabase.table('inventory').select('flavor').execute()
                db_flavors = [item['flavor'] for item in response.data]
                # Combine default flavors with database flavors
                all_flavors = list(set(self.flavors + db_flavors))
                all_flavors.sort()
                return all_flavors
            else:
                # From local storage
                inventory = self._load_from_file('data/inventory.json')
                all_flavors = list(set(self.flavors + list(inventory.keys())))
                all_flavors.sort()
                return all_flavors
        except Exception as e:
            print(f"Error getting flavors: {e}")
            return self.flavors


    def update_inventory(self, flavor: str, count: int, operation: str = 'set') -> bool:
        """Update inventory count for a specific flavor"""
        try:
            current_inventory = self.get_inventory()
            
            if operation == 'add':
                new_count = current_inventory.get(flavor, 0) + count
            elif operation == 'subtract':
                new_count = max(0, current_inventory.get(flavor, 0) - count)
            else:  # set
                new_count = count
            
            if supabase:
                # Check if flavor exists first
                existing = supabase.table('inventory').select('*').eq('flavor', flavor).execute()
                
                if existing.data:
                    # Update existing record
                    supabase.table('inventory').update({
                        'count': new_count,
                        'updated_at': datetime.now().isoformat()
                    }).eq('flavor', flavor).execute()
                else:
                    # Insert new record
                    supabase.table('inventory').insert({
                        'flavor': flavor,
                        'count': new_count,
                        'updated_at': datetime.now().isoformat()
                    }).execute()
            else:
                # Fallback to JSON file
                current_inventory[flavor] = new_count
                self._save_to_file('data/inventory.json', current_inventory)
            
            return True
        except Exception as e:
            print(f"Error updating inventory: {e}")
            return False
    
    
    def record_sale(self, flavor: str, quantity: int) -> bool:
        """Record a sale and update inventory"""
        try:
            current_inventory = self.get_inventory()
            
            if current_inventory.get(flavor, 0) < quantity:
                return False  # Not enough stock
            
            # Record sale
            sale_data = {
                'flavor': flavor,
                'quantity': quantity,
                'sale_date': date.today().isoformat(),
                'timestamp': datetime.now().isoformat()
            }
            
            if supabase:
                supabase.table('sales').insert(sale_data).execute()
            else:
                # Fallback to JSON file
                sales = self._load_from_file('data/sales.json')
                sales.append(sale_data)
                self._save_to_file('data/sales.json', sales)
            
            # Update inventory
            self.update_inventory(flavor, quantity, 'subtract')
            return True
            
        except Exception as e:
            print(f"Error recording sale: {e}")
            return False
    
    def get_sales_data(self, days: int = 30) -> List[Dict]:
        """Get sales data for the specified number of days"""
        try:
            if supabase:
                response = supabase.table('sales').select('*').order('timestamp', desc=True).limit(100).execute()
                return response.data
            else:
                # Fallback to JSON file
                sales = self._load_from_file('data/sales.json')
                # Sort by timestamp, newest first
                return sorted(sales, key=lambda x: x.get('timestamp', ''), reverse=True)
        except Exception as e:
            print(f"Error loading sales data: {e}")
            return []
    
    def get_low_stock_items(self, threshold: int = 10) -> List[Dict]:
        """Get items with stock below threshold"""
        inventory = self.get_inventory()
        return [
            {'flavor': flavor, 'count': count}
            for flavor, count in inventory.items()
            if count < threshold
        ]
    
    def _load_from_file(self, filename: str) -> Dict:
        """Load data from JSON file (fallback method)"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading from {filename}: {e}")
        
        # Return appropriate default based on file type
        if 'inventory' in filename:
            return {flavor: 0 for flavor in self.flavors}
        else:
            return []
    
    def _save_to_file(self, filename: str, data) -> None:
        """Save data to JSON file (fallback method)"""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving to {filename}: {e}")



# Initialize inventory manager
inventory_manager = InventoryManager()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    inventory = inventory_manager.get_inventory()
    low_stock = [{'flavor': flavor, 'count': count} for flavor, count in inventory.items() if 0 < count < 10]
    
    # Calculate totals
    total_items = sum(inventory.values())
    total_flavors = len([count for count in inventory.values() if count > 0])
    
    return render_template('dashboard.html', 
                         inventory=inventory,
                         low_stock=low_stock,
                         total_items=total_items,
                         total_flavors=total_flavors,
                         flavors=inventory_manager.flavors)

@app.route('/debug')
def debug_supabase():
    """Debug Supabase connection"""
    debug_info = {
        'supabase_connected': supabase is not None,
        'supabase_url_set': bool(SUPABASE_URL and SUPABASE_URL != 'YOUR_SUPABASE_URL_HERE'),
        'supabase_key_set': bool(SUPABASE_KEY and SUPABASE_KEY != 'YOUR_SUPABASE_ANON_KEY_HERE'),
        'storage_mode': 'Database' if supabase else 'Local JSON'
    }
    
    if supabase:
        try:
            # Test database connection
            response = supabase.table('inventory').select('*').limit(1).execute()
            debug_info['db_test'] = 'SUCCESS'
            debug_info['db_records'] = len(response.data)
        except Exception as e:
            debug_info['db_test'] = f'FAILED: {str(e)}'
    
    return jsonify(debug_info)

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    """Add stock to inventory"""
    if request.method == 'POST':
        flavor = request.form.get('flavor')
        count = int(request.form.get('count', 0))
        
        if flavor and count > 0:
            if inventory_manager.update_inventory(flavor, count, 'add'):
                flash(f'Successfully added {count} {flavor} ice creams to inventory!', 'success')
            else:
                flash('Error adding stock. Please try again.', 'error')
        else:
            flash('Please provide valid flavor and count.', 'error')
        
        return redirect(url_for('dashboard'))
    
    return render_template('add_stock.html', flavors=inventory_manager.get_all_flavors())

@app.route('/record_sale', methods=['GET', 'POST'])
def record_sale():
    """Record a sale"""
    if request.method == 'POST':
        flavor = request.form.get('flavor')
        quantity = int(request.form.get('quantity', 0))
        
        if flavor and quantity > 0:
            if inventory_manager.record_sale(flavor, quantity):
                flash(f'Successfully recorded sale: {quantity} {flavor} ice creams!', 'success')
            else:
                flash('Not enough stock or error recording sale.', 'error')
        else:
            flash('Please provide valid flavor and quantity.', 'error')
        
        return redirect(url_for('dashboard'))
    
    inventory = inventory_manager.get_inventory()
    return render_template('record_sale.html', 
                         flavors=inventory_manager.get_all_flavors(),
                         inventory=inventory)

@app.route('/manage_flavors', methods=['GET', 'POST'])
def manage_flavors():
    """Manage flavors page"""
    if request.method == 'POST':
        new_flavor = request.form.get('new_flavor', '').strip().title()
        
        if new_flavor:
            if inventory_manager.add_new_flavor(new_flavor):
                flash(f'Successfully added new flavor: {new_flavor}!', 'success')
            else:
                flash(f'Flavor "{new_flavor}" already exists or error occurred.', 'error')
        else:
            flash('Please enter a valid flavor name.', 'error')
        
        return redirect(url_for('manage_flavors'))
    
    all_flavors = inventory_manager.get_all_flavors()
    inventory = inventory_manager.get_inventory()
    
    return render_template('manage_flavors.html', 
                         all_flavors=all_flavors,
                         inventory=inventory)


@app.route('/sales_report')
def sales_report():
    """Sales report page"""
    sales_data = inventory_manager.get_sales_data()
    
    # Process sales data for reporting
    today_sales = []
    flavor_totals = {}
    total_sales_today = 0
    
    today = date.today().isoformat()
    
    for sale in sales_data:
        sale_date = sale.get('sale_date', '')
        if sale_date == today:
            today_sales.append(sale)
            total_sales_today += sale['quantity']
        
        flavor = sale['flavor']
        if flavor in flavor_totals:
            flavor_totals[flavor] += sale['quantity']
        else:
            flavor_totals[flavor] = sale['quantity']
    
    # Sort flavors by sales
    top_flavors = sorted(flavor_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return render_template('sales_report.html',
                         today_sales=today_sales,
                         total_sales_today=total_sales_today,
                         top_flavors=top_flavors,
                         recent_sales=sales_data[:20])

@app.route('/api/inventory')
def api_inventory():
    """API endpoint for inventory data"""
    return jsonify(inventory_manager.get_inventory())

@app.route('/api/add_stock', methods=['POST'])
def api_add_stock():
    """API endpoint to add stock"""
    data = request.get_json()
    flavor = data.get('flavor')
    count = int(data.get('count', 0))
    
    if inventory_manager.update_inventory(flavor, count, 'add'):
        return jsonify({'success': True, 'message': f'Added {count} {flavor} to inventory'})
    else:
        return jsonify({'success': False, 'message': 'Error adding stock'}), 400

@app.route('/api/record_sale', methods=['POST'])
def api_record_sale():
    """API endpoint to record sale"""
    data = request.get_json()
    flavor = data.get('flavor')
    quantity = int(data.get('quantity', 0))
    
    if inventory_manager.record_sale(flavor, quantity):
        return jsonify({'success': True, 'message': f'Recorded sale: {quantity} {flavor}'})
    else:
        return jsonify({'success': False, 'message': 'Not enough stock or error recording sale'}), 400

if __name__ == '__main__':
    print("🍦 Starting Havmor Ice Cream Inventory System...")
    print("📍 Dashboard: http://localhost:5000")
    print("📱 Mobile friendly interface ready!")
    print("💾 Data storage: Local JSON files (upgrade to Supabase anytime)")
    print("-" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)