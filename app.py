from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import urllib.parse 
from sqlalchemy import extract
import os
from flask import send_file

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pansala_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///temple.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "කරුණාකර පද්ධතියට ඇතුල් වන්න."
login_manager.login_message_category = "warning"

# --- Database Models (වගු) ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False) # අලුතින් එකතු කළ කොටස
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False) 
    quantity = db.Column(db.Integer, default=0)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False) 
    quantity = db.Column(db.Integer, nullable=False)
    date_time = db.Column(db.DateTime, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=True) # විකිණීම් සඳහා
    description = db.Column(db.String(255), nullable=True) # හානි වූ හේතුව හෝ වෙනත් විස්තර
    
    item = db.relationship('Item')
    user = db.relationship('User')

class Lending(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    borrower_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    issued_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow) # මේ පේළිය අලුතින් එකතු කළා
    status = db.Column(db.String(20), default='borrowed') 
    items = db.relationship('LendingItem', backref='lending', lazy=True)

class LendingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lending_id = db.Column(db.Integer, db.ForeignKey('lending.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    issued_qty = db.Column(db.Integer, nullable=False)
    damaged_qty = db.Column(db.Integer, default=0) # හානි වූ/අඩු ප්‍රමාණය
    
    item = db.relationship('Item') # භාණ්ඩයේ නම ලබා ගැනීමට

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes (පිටු) ---
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        # User කෙනෙක් ඉන්නවද සහ Password එක හරිද කියලා බලනවා
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('පරිශීලක නම හෝ මුරපදය වැරදියි. නැවත උත්සාහ කරන්න.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ඔබ පද්ධතියෙන් සාර්ථකව ඉවත් විය.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    # Owner ට විතරක් මේ පිටුවට යන්න දෙනවා
    if current_user.role != 'owner':
        flash('ඔබට මෙම පිටුවට පිවිසීමට අවසර නැත.', 'danger')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_fullname = request.form.get('full_name')
        new_password = request.form.get('password')
        
        # මේ නමින් ගිණුමක් කලින් තියෙනවද කියලා බලනවා
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user:
            flash('මෙම පිවිසුම් නම දැනටමත් පද්ධතියේ ඇත. වෙනත් නමක් යොදන්න.', 'danger')
        else:
            hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
            new_user = User(username=new_username, full_name=new_fullname, password=hashed_password, role='user')
            db.session.add(new_user)
            db.session.commit()
            flash(f'{new_fullname} සඳහා නව ගිණුම සාර්ථකව සෑදුවා!', 'success')
            
    # දැනට පද්ධතියේ ඉන්න සාමාන්‍ය පරිශීලකයින්ගේ ලැයිස්තුව ගන්නවා
    users = User.query.filter_by(role='user').all()
    return render_template('manage_users.html', users=users)


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        # දැනට තියෙන Password එක හරිද කියලා බලනවා
        if check_password_hash(current_user.password, current_password):
            # හරි නම් අලුත් Password එක Database එකට දානවා
            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
            db.session.commit()
            flash('ඔබගේ මුරපදය සාර්ථකව වෙනස් කරන ලදී!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('දැනට භාවිතා කරන මුරපදය වැරදියි. නැවත උත්සාහ කරන්න.', 'danger')
            
    return render_template('change_password.html')

@app.route('/issue', methods=['GET', 'POST'])
@login_required
def issue_items():
    if request.method == 'POST':
        issue_type = request.form.get('issue_type')
        
        # 1. දාන මාන සඳහා (WhatsApp පණිවිඩය)
        if issue_type == 'dana':
            borrower_name = request.form.get('borrower_name')
            phone_number = request.form.get('phone_number')
            area = request.form.get('area')
            
            new_lending = Lending(borrower_name=borrower_name, phone_number=phone_number, location=area, issued_by=current_user.id)
            db.session.add(new_lending)
            db.session.flush() 
            
            issued_items_text = ""
            item_counter = 1  # භාණ්ඩ සඳහා අංක දැමීමට
            
            dana_items = {
                'පිඟන්': request.form.get('plates_qty', 0, type=int),
                'කෝප්ප': request.form.get('cups_qty', 0, type=int),
                'වීදුරු': request.form.get('glasses_qty', 0, type=int),
                'කිරි කප්': request.form.get('milkcups_qty', 0, type=int),
                'හැඳි': request.form.get('spoons_qty', 0, type=int),
                'අත හෝදන භාජන': request.form.get('basins_qty', 0, type=int)
            }
            
            # Form එකෙන් එන අමතර භාණ්ඩ සියල්ල ලබාගැනීම
            for key, value in request.form.items():
                if key.startswith('extra_qty_'):
                    item_name = key.replace('extra_qty_', '')
                    qty = int(value) if value and value.strip() else 0
                    if qty > 0:
                        dana_items[item_name] = qty
            
            for item_name, qty in dana_items.items():
                if qty > 0:
                    item = Item.query.filter_by(name=item_name).first()
                    if not item:
                        item = Item(name=item_name, category='returnable', quantity=0)
                        db.session.add(item)
                        db.session.flush()
                    
                    lending_item = LendingItem(lending_id=new_lending.id, item_id=item.id, issued_qty=qty)
                    db.session.add(lending_item)
                    
                    if current_user.role != 'secret':
                        item.quantity -= qty
                        
                    # අංක සහිතව ලැයිස්තුව සැකසීම (උදා: 1. පිඟන් - 4)
                    issued_items_text += f"{item_counter}. {item_name} - {qty}\n"
                    item_counter += 1
                    
            db.session.commit()
            
            # Encoding ගැටළුව විසඳීමට Emojis ඉවත් කර ඇත
            whatsapp_msg = (
                "*ශ්‍රී බෝධිරාජාරාම විහාරස්ථානය*\n"
                "භාණ්ඩ නිකුත් කිරීමේ සටහන\n\n"
                f"නම: {borrower_name}\n"
                f"ප්‍රදේශය: {area}\n"
                f"අංකය: {phone_number}\n\n"
                "*ලබාගත් භාණ්ඩ:*\n"
                f"{issued_items_text}\n"
                f"සටහන් කළේ: {current_user.full_name}"
            )
            
            encoded_msg = urllib.parse.quote(whatsapp_msg)
            formatted_phone = phone_number.strip()
            if formatted_phone.startswith('0'):
                formatted_phone = '94' + formatted_phone[1:]
                
            whatsapp_url = f"https://wa.me/{formatted_phone}?text={encoded_msg}"
            flash('භාණ්ඩ නිකුත් කිරීම සටහන් කළා.', 'success')
            return redirect(whatsapp_url)
            
        # 2. පිරිකර සහ වෙනත්
        elif issue_type == 'other':
            item_name = request.form.get('item_name')
            category = request.form.get('category', 'consumable')
            qty = request.form.get('quantity', 1, type=int)
            reason = request.form.get('reason')
            amount = request.form.get('amount', 0.0, type=float)
            
            if item_name:
                item = Item.query.filter_by(name=item_name).first()
                if not item:
                    item = Item(name=item_name, category=category, quantity=0)
                    db.session.add(item)
                    db.session.flush()
                
                if current_user.role != 'secret':
                    item.quantity -= qty
                    new_tx = Transaction(item_id=item.id, user_id=current_user.id, action_type=reason, quantity=qty, amount=amount)
                    db.session.add(new_tx)
                    
                db.session.commit()
                flash(f'{item_name} පද්ධතියේ සටහන් කළා!', 'success')
        
        return redirect(url_for('dashboard'))
        
    items = Item.query.all()
    return render_template('issue.html', items=items)

# app.py ගොනුවේ අදාළ කොටස පමණි

from sqlalchemy import extract # මෙය import කොටසට එකතු කරන්න

@app.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # මාසය තේරීමට
    selected_month = request.args.get('month', current_month, type=int)
    selected_year = request.args.get('year', current_year, type=int)

    if request.method == 'POST':
        item_name = request.form.get('name')
        item_category = request.form.get('category')
        added_qty = request.form.get('quantity', 0, type=int)
        
        # භාණ්ඩය කලින් තියෙනවද බලනවා
        existing_item = Item.query.filter_by(name=item_name).first()
        if existing_item:
            existing_item.quantity += added_qty
            new_tx = Transaction(item_id=existing_item.id, user_id=current_user.id, action_type='add_stock', quantity=added_qty)
            db.session.add(new_tx)
            flash(f'{item_name} සඳහා තොගය සාර්ථකව යාවත්කාලීන කළා.', 'success')
        else:
            new_item = Item(name=item_name, category=item_category, quantity=added_qty)
            db.session.add(new_item)
            db.session.flush()
            new_tx = Transaction(item_id=new_item.id, user_id=current_user.id, action_type='add_new', quantity=added_qty)
            db.session.add(new_tx)
            flash(f'{item_name} සාර්ථකව ගබඩාවට එකතු කළා.', 'success')
            
        db.session.commit()
        return redirect(url_for('inventory', month=selected_month, year=selected_year))
        
    items = Item.query.all()
    
    # මාසික සාරාංශය සෑදීම
    monthly_summary = []
    for item in items:
        # තෝරාගත් මාසයට අදාළ ගනුදෙනු
        transactions = Transaction.query.filter(
            Transaction.item_id == item.id,
            extract('month', Transaction.date_time) == selected_month,
            extract('year', Transaction.date_time) == selected_year
        ).all()
        
        added_this_month = sum(tx.quantity for tx in transactions if tx.action_type in ['add_stock', 'add_new'])
        # issued_this_month සඳහා action_type එක 'dana' හෝ වෙනත් නිකුත් කිරීමක් නම් පමණක් සලකන්න (මෙය ඔබගේ transaction action_types මත රඳා පවතී)
        # දැනට සරලව සෘණ නොවන action_types හැර අනෙක්වා නිකුත් කිරීම් ලෙස සලකමු (මෙය ඔබගේ කේතයට අනුව වෙනස් විය හැක)
        issued_this_month = sum(tx.quantity for tx in transactions if tx.action_type not in ['add_stock', 'add_new']) 
        
        # මාසය මුල තිබූ ප්‍රමාණය (දැනට ඇති ප්‍රමාණය - එකතු කළ + නිකුත් කළ)
        initial_qty = item.quantity - added_this_month + issued_this_month 
        
        monthly_summary.append({
            'item': item,
            'initial_qty': initial_qty,
            'added_this_month': added_this_month,
            'issued_this_month': issued_this_month,
            'current_qty': item.quantity
        })

    return render_template('inventory.html', items=items, summary=monthly_summary, selected_month=selected_month, selected_year=selected_year)

@app.route('/edit_user/<int:user_id>', methods=['POST'])
@login_required
def edit_user(user_id):
    # Owner ට හැර වෙන කාටවත් මෙය කළ නොහැක
    if current_user.role != 'owner':
        flash('මෙම ක්‍රියාව කිරීමට ඔබට අවසර නොමැත.', 'danger')
        return redirect(url_for('dashboard'))
        
    user = User.query.get_or_404(user_id)
    
    # පෝරමයෙන් ලබාගන්නා නව දත්ත
    user.full_name = request.form.get('full_name')
    user.username = request.form.get('username')
    new_password = request.form.get('password')
    
    # මුරපදය කොටුවේ යමක් ටයිප් කර ඇත්නම් පමණක් එය මාරු කරයි
    if new_password and new_password.strip():
        # මෙතැන 'password_hash' වෙනුවට 'password' ලෙස නිවැරදි කර ඇත
        user.password = generate_password_hash(new_password)
        
    db.session.commit()
    flash(f'{user.full_name} ගේ ගිණුමේ විස්තර සාර්ථකව වෙනස් කරන ලදී.', 'success')
    
    return redirect(url_for('manage_users'))

@app.route('/returns', methods=['GET'])
@login_required
def returns():
    # භාර නොදුන් (borrowed තත්ත්වයේ ඇති) ලැයිස්තුව ලබා ගැනීම
    pending_lendings = Lending.query.filter_by(status='borrowed').order_by(Lending.id.desc()).all()
    return render_template('return.html', lendings=pending_lendings)

@app.route('/mark_returned/<int:lending_id>', methods=['POST'])
@login_required
def mark_returned(lending_id):


    lending = Lending.query.get_or_404(lending_id)
    lending.status = 'returned'
    
    returned_details_text = ""
    item_counter = 1
    
    # එක් එක් භාණ්ඩය සඳහා හානි වූ ප්‍රමාණයන් ලබාගෙන ගබඩාව යාවත්කාලීන කිරීම
    for l_item in lending.items:
        damaged_qty = request.form.get(f'damaged_qty_{l_item.id}', 0, type=int)
        l_item.damaged_qty = damaged_qty
        
        returned_qty = l_item.issued_qty - damaged_qty
        
        item = Item.query.get(l_item.item_id)
        if item:
            if returned_qty > 0:
                item.quantity += returned_qty
                new_tx = Transaction(item_id=item.id, user_id=current_user.id, action_type='returned', quantity=returned_qty)
                db.session.add(new_tx)
            
            if damaged_qty > 0:
                new_tx_damage = Transaction(item_id=item.id, user_id=current_user.id, action_type='damaged', quantity=damaged_qty)
                db.session.add(new_tx_damage)
                
            # WhatsApp පණිවිඩයට භාණ්ඩ විස්තර එකතු කිරීම
            returned_details_text += f"{item_counter}. {item.name} - ගෙනගිය: {l_item.issued_qty} | අඩු/හානි: {damaged_qty}\n"
            item_counter += 1
            
    db.session.commit()
    
    # WhatsApp පණිවිඩය සෑදීම
    whatsapp_msg = (
        "🙏 *ශ්‍රී බෝධිරාජාරාම විහාරස්ථානය*\n"
        "✅ *භාණ්ඩ ආපසු භාරගැනීමේ සටහන*\n\n"
        f"👤 නම: {lending.borrower_name}\n\n"
        "ඔබ රැගෙන ගිය භාණ්ඩ සාර්ථකව විහාරස්ථානයට භාරගන්නා ලදී. ඔබගේ පින්කම් කටයුතු සාර්ථක වේවා! 🙏\n\n"
        "📋 *භාරදුන් විස්තරය:*\n"
        f"{returned_details_text}\n"
        f"✍️ සටහන් කළේ: {current_user.full_name}"
    )
    
    import urllib.parse
    encoded_msg = urllib.parse.quote(whatsapp_msg)
    formatted_phone = lending.phone_number.strip()
    if formatted_phone.startswith('0'):
        formatted_phone = '94' + formatted_phone[1:]
        
    whatsapp_url = f"https://wa.me/{formatted_phone}?text={encoded_msg}"
    
    flash(f'{lending.borrower_name} ගේ භාණ්ඩ භාරගැනීම සාර්ථකයි.', 'success')
    # මෙතනින් තමයි WhatsApp එකට යොමු කරන්නේ
    return redirect(whatsapp_url)

@app.route('/reports', methods=['GET'])
@login_required
def reports():
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    selected_month = request.args.get('month', current_month, type=int)
    selected_year = request.args.get('year', current_year, type=int)
    
    # 1. දිනපතා ගනුදෙනු
    transactions = Transaction.query.filter(
        extract('month', Transaction.date_time) == selected_month,
        extract('year', Transaction.date_time) == selected_year
    ).order_by(Transaction.date_time.desc()).all()
    
    # 2. වත්මන් තොගය
    stock = Item.query.order_by(Item.category, Item.name).all()
    
    # 3. දාන මාන ඉතිහාසය
    lendings_history = Lending.query.order_by(Lending.id.desc()).all()
    
    # 4. හානි වූ භාණ්ඩ
    damaged_history = Transaction.query.filter(
        Transaction.action_type == 'damaged',
        extract('month', Transaction.date_time) == selected_month,
        extract('year', Transaction.date_time) == selected_year
    ).order_by(Transaction.id.desc()).all()

    # 5. පිරිකර සහ වෙනත් ගනුදෙනු (විකිණීම් / පරිභෝජන)
    other_transactions = Transaction.query.filter(
        Transaction.action_type.in_(['sale', 'පරිභෝජනය සඳහා']),
        extract('month', Transaction.date_time) == selected_month,
        extract('year', Transaction.date_time) == selected_year
    ).order_by(Transaction.id.desc()).all()
    
    return render_template('reports.html', 
                           transactions=transactions, 
                           stock=stock, 
                           lendings=lendings_history,
                           damaged=damaged_history,
                           others=other_transactions,
                           selected_month=selected_month, 
                           selected_year=selected_year)

@app.route('/remove_damage/<int:item_id>', methods=['POST'])
@login_required
def remove_damage(item_id):
    item = Item.query.get_or_404(item_id)
    damaged_qty = request.form.get('damaged_qty', 0, type=int)
    reason = request.form.get('reason', '')
    
    if damaged_qty > 0 and damaged_qty <= item.quantity:
        item.quantity -= damaged_qty
        # හානි වූ බව සහ හේතුව සටහන් කිරීම
        new_tx = Transaction(item_id=item.id, user_id=current_user.id, action_type='damaged', quantity=damaged_qty, description=reason)
        db.session.add(new_tx)
        db.session.commit()
        flash(f'{item.name} භාණ්ඩයෙන් {damaged_qty} ක් ඉවත් කළ බව සටහන් කළා.', 'success')
    else:
        flash('ඇතුළත් කළ ප්‍රමාණය වැරදියි හෝ ගබඩාවේ ඇති ප්‍රමාණයට වඩා වැඩියි.', 'danger')
        
    return redirect(url_for('inventory'))


@app.route('/admin/backup')
@login_required
def backup_database():
    # ප්‍රධාන ඇඩ්මින්ට (owner) පමණක් බැකප් ලබා ගැනීමට සැලසීම
    if current_user.role != 'owner':
        flash('මෙම ක්‍රියාව කිරීමට ඔබට අවසර නැත.', 'danger')
        return redirect(url_for('dashboard'))
        
    db_path = os.path.join(app.instance_path, 'temple.db')
    if os.path.exists(db_path):
        return send_file(db_path, as_attachment=True, download_name='temple_backup.db')
    else:
        flash('ඩේටාබේස් ගොනුව හමුවුණේ නැත!', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/admin/restore', methods=['POST'])
@login_required
def restore_database():
    # ප්‍රධාන ඇඩ්මින්ට (owner) පමණක් රීස්ටෝර් කිරීමට සැලසීම
    if current_user.role != 'owner':
        flash('මෙම ක්‍රියාව කිරීමට ඔබට අවසර නැත.', 'danger')
        return redirect(url_for('dashboard'))
        
    if 'backup_file' not in request.files:
        flash('බැකප් ගොනුවක් තෝරා නැත.', 'danger')
        return redirect(url_for('dashboard'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('ගොනුවේ නම හිස්ය.', 'danger')
        return redirect(url_for('dashboard'))
    
    if file and file.filename.endswith('.db'):
        db_path = os.path.join(app.instance_path, 'temple.db')
        file.save(db_path)
        flash('දත්ත ගබඩාව සාර්ථකව ප්‍රතිස්ථාපනය (Restore) කරන ලදී! කරුණාකර නැවත ලොග් වන්න.', 'success')
        return redirect(url_for('logout'))
    else:
        flash('කරුණාකර නිවැරදි .db වර්ගයේ ගොනුවක් තෝරන්න.', 'danger')
        return redirect(url_for('dashboard'))

# --- මෙන්න මේ කොටසට උඩින් තමයි ඉහත කෝඩ් එක දාන්න ඕනේ ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # (ඉතිරි කෝඩ් එක සුපුරුදු පරිදි පවතී...)    

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Owner සහ Secret ගිණුම් ස්වයංක්‍රීයව හැදීම
        if not User.query.filter_by(role='owner').first():
            # Owner ගිණුම (ඔබගේ ගිණුම)
            owner_pass = generate_password_hash('Owner@123', method='pbkdf2:sha256')
            owner = User(username='admin', full_name='පඤ්ඤාතිස්ස ස්වාමීන් වහන්සේ', password=owner_pass, role='owner')
            db.session.add(owner)
            
            # රහස්‍ය (Secret) ගිණුම
            secret_pass = generate_password_hash('Secret@123', method='pbkdf2:sha256')
            secret_user = User(username='secret_admin', full_name='විශේෂ ගිණුම', password=secret_pass, role='secret')
            db.session.add(secret_user)
            
            db.session.commit()
            print("මූලික ගිණුම් සාර්ථකව නිර්මාණය කරන ලදී!")

    app.run(debug=True)