from flask import Flask, flash, render_template, request, redirect, url_for, session, Response, make_response
from flask_session import Session
import mysql.connector
import random
import os, shutil
import re
from sendemail import sendmail
import smtplib
from werkzeug.utils import secure_filename
from datetime import datetime
import yaml

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract


pytesseract.pytesseract.tesseract_cmd = r'Tesseract-OCR\tesseract.exe'

UPLOAD_FOLDER = os.path.join('static', 'uploads')



# allow files of a specific type
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

app = Flask(__name__)

app.jinja_env.globals.update(zip=zip)

app.secret_key = 'a'



app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
Session(app)

db = yaml.load(open('db.yaml'), Loader=yaml.FullLoader)

mydb = mysql.connector.connect(host=db['mysql_host'], user=db['mysql_user'], port=db['mysql_port'], password=db['mysql_password'], database=db['mysql_db'])


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def tablename(email):
    lst = re.split("[@ ! # $ % & . * + \- / = ? ^ _]",email)
    tname = ''.join(lst)
    return tname

def ocr_core(filename):
    # print("a+b    " + filepath)
    """
    This function will handle the core OCR processing of images.
    """
    text = pytesseract.image_to_string(Image.open(filename))  # We'll use Pillow's Image class to open the image and pytesseract to detect the string in the image
    return text


@app.route('/')
def home():
    return render_template("index.html")

@app.route('/login')
def login():
    if session.get("username"):
        # if there in the session then redirect to the main page
        flash('You Are Already Logged In !')
        return redirect(url_for("main_page"))
    return render_template("login.html")

@app.route('/login', methods = ["GET", "POST"])
def get_login():
    global userid
    msg = ''

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        mydb.reconnect()

        mycursor = mydb.cursor()
        mycursor.execute('select * from users where email = %s and password = %s', (email, password ),)
        account = mycursor.fetchone()
        
        tname = ''
        if account:
            session['loggedin'] = True
            session['id'] = account[0]
            session['name'] = account[1].split()[0]
            userid=  account[0]
            session['username'] = account[2]
            tname = tablename(account[2])
            session["tname"] = tname
            flash('Logged in successfully !')
            return redirect(url_for('main_page'))
        else:
            msg = 'Incorrect Email / Password !'
    return render_template('login.html', msg = msg)

@app.route('/register')
def register():
    return render_template("register.html")

@app.route('/register', methods = ["GET", "POST"])
def get_register():
    msg = ''
    
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        dob = request.form["dob"]
        phone = request.form["phone"]
        password = request.form["password"]
        confirm_password = request.form["confirm-password"]
        count = 0
        if len(password) < 8:
            return render_template("register.html", msg="Password Should Have Minimum 8 Characters")
        if password != confirm_password:
            msg = 'Password should be same as Confirm Password'
            return render_template("register.html", msg=msg)
        val = (name, email, dob, phone, password, count)
        sql = "insert into users (name, email, dob, phone, password, count) values (%s, %s, %s, %s, %s, %s)"
        try:
            tname = ''
            mydb.reconnect()
            mycursor = mydb.cursor()
            mycursor.execute(sql, val)
            mydb.commit()
            tname = tablename(email)
            session["tname"] = tname
            mycursor.execute("CREATE TABLE IF NOT EXISTS {} (id INT(100) PRIMARY KEY AUTO_INCREMENT, name VARCHAR(150), phone VARCHAR(20), website VARCHAR(150), email VARCHAR(150), address VARCHAR(300), image mediumblob not null, upload_date date)".format(tname))
            mydb.commit()
            SUBJECT = "Welcome To Smart ID Scanner"
            TEXT = "Hello "+name + ",\n\n"+ """Thanks for registring at Smart ID Scanner Website """ 
            sendmail(TEXT,email,SUBJECT)
            return render_template("register.html", msg="Registration Successful... Login to Continue")
        except mysql.connector.Error as e:
            print(e)
            warn = "Mobile Number Or Email Already Exists"
            return render_template('register.html', msg=warn)

@app.route('/main_page')
def main_page():
    if not session.get("username"):
        # if not there in the session then redirect to the login page
        return redirect(url_for("login"))
    temp = str(session.get("username"))
    mydb.reconnect()

    mycursor = mydb.cursor()
    mycursor.execute("select count from users where email = '{}' ".format(temp))
    records = mycursor.fetchone()
    records = records[0]
    welcome = "Welcome, " + str(session.get("name")) + "!"
    return render_template("main.html", welcome=welcome, records=records)
        

@app.route('/forgot_password')
def forgot_password():
    return render_template("forgot_password.html")

@app.route('/forgot_password', methods = ["GET", "POST"])
def enter_code():

    if request.method == "POST":
        email = request.form["email"]
        mydb.reconnect()

        mycursor = mydb.cursor()
        mycursor.execute("select * from users where email = '{}' ".format(email))
        account = mycursor.fetchone()
        
        if account:
            name = account[1]
            code = random.randint(100000, 999999)
            session["code"] = code
            session["username"] = email
            SUBJECT = "Verification Code To Reset Password"
            TEXT = "Hello "+name + ",\n\n"+ """Your Verification Code For Password Reset Is \n\n """ + str(code) + """\n\n\nRegards,\nSmart ID Scanner Team """
            sendmail(TEXT,email,SUBJECT)
            return redirect(url_for("reset_password"))

        else:
            return render_template("forgot_password.html", msg="Account Doesn't Exist!")


@app.route('/reset_password')
def reset_password():
    if not session.get("code"):
        # if not there in the session then redirect to the login page
        return redirect(url_for("login"))
    return render_template("reset_password.html")


@app.route('/reset_password', methods = ["GET", "POST"])
def check_code():
    if request.method == "POST":
        code = request.form["code"]
        password = request.form["password"]
        confirm_password = request.form["confirm-password"]
        try:
            code = int(code)
            if not session.get("code"):
                # if not there in the session then redirect to the login page
                return redirect(url_for("login"))
            if code != session.get("code"):
                return render_template("reset_password.html", msg="Verification Code Is Incorrect!")
            if len(password) < 8:
                return render_template("reset_password.html", msg="Password Should Have Minimum 8 Characters")
            if password != confirm_password:
                return render_template("reset_password.html", msg="Password should be same as Confirm Password")
            email = session.get("username")
            mydb.reconnect()
            mycursor = mydb.cursor()
            mycursor.execute('update users set password = %s where email = %s', (password, email ),)
            mydb.commit()
            session.pop('code', None)
            session.pop('username', None)
            return render_template("reset_password.html", msg="Password Updated Successfully... You Can Now Login with Your New Password")
        except ValueError:
            return render_template("reset_password.html", msg="Verification Code Cannot Contain Alphabets And Special Characters!")


@app.route('/add_records')
def add_records():
    if not session.get("username"):
        # if not there in the session then redirect to the login page
        return redirect(url_for("login"))
    return render_template("add_records.html", img_src=None)


@app.route('/add_records', methods = ["GET", "POST"])
def add_image():
    if request.method == "POST":
        
        name = request.form['name']
        file = request.files['file']
        print(file)
        # if no file is selected
        if file.filename == '':
            return render_template('add_records.html', msg='No file selected', img_src=None)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # filepath1 = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            # print("filepath1   "+ filepath1)
            filepath = os.getcwd() + os.path.join(app.config['UPLOAD_FOLDER'], filename)
            # print(filepath)
            # print(UPLOAD_FOLDER)
            # filepath = filepath.replace("|","")
            

            # call the OCR function on it
            extracted_text = ocr_core(file)
            lst = extracted_text.split("\n")
            string = extracted_text.replace("\n", " ")
            
            if lst == ['\x0c']:
                os.remove(filepath)
                return render_template("add_records.html", msg="Could Not Extract Data From Image", img_src=None)

            emails = re.findall(r"[A-Za-z0-9\.\-+_]+@[A-Za-z0-9\.\-+_]+\.[A-Za-z]+", string)
            
            phone = ''
            for i in lst:
                if (i.startswith("+") and int(i[-1])) or (i.startswith("(") and int(i[-1])):
                    phone = i
                    break
                else:
                    try:
                        if int(i[0]):
                            if " " in i:
                                temp = i.replace(' ','')
                            elif "." in i:
                                temp = i.replace('.','')
                            elif "-" in i:
                                temp = i.replace('-','')
                            if int(temp):
                                phone = i
                                break
                    except:
                        continue

            website = ''

            for i in lst:
                if i.lower().startswith("www.") or i.lower().startswith("http") or i.lower().endswith(".in"):
                    website = i
                    break

            address = max(lst, key=len)

            if len(address) < 10:
                address = ''
            
            if emails == []:
                emails = ''
            else:
                emails = emails[0]
            

            if emails == '' and phone == '' and address == '' and website == '':
                os.remove(filepath)
                return render_template("add_records.html", msg="Could Not Extract Data From Image", img_src=None)

            folder = '/static/uploads/' + filename
            session["folder"] = folder

            # extract the text and display it
            return render_template("add_records.html", img_src=folder, name=name, email=emails, address=address, phone=phone, website=website)
                                
    elif request.method == 'GET':
        return render_template('add_records.html')



@app.route('/upload_data')
def upload_data():
    if not session.get("username"):
        # if not there in the session then redirect to the login page
        return redirect(url_for("login"))
    render_template("add_records.html")

@app.route('/upload_data', methods = ["GET", "POST"])
def extract():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        website = request.form["website"]
        cwd = os.getcwd() + session.get("folder").replace("/","\|")
        cwd = cwd.replace("|","")
        
        with open(cwd, 'rb') as f:
            image = f.read()
        if email == '':
            email = "NA"
        if phone == '':
            phone = "NA"
        if address == '':
            address = "NA"
        if website == '':
            website = "NA"
        
        tname = session.get("tname")

        upload_date = str(datetime.date(datetime.now()))
        
        val = (name, phone, website, email, address, image, upload_date)
        sql = "insert into {} (name, phone, website, email, address, image, upload_date) values (%s, %s, %s, %s, %s, %s, %s)".format(tname)

        try:
            mydb.reconnect()
            mycursor = mydb.cursor()
            mycursor.execute(sql, val)
            mydb.commit()
            temp = str(session.get("username"))

            mydb.reconnect()
            mycursor = mydb.cursor()
            mycursor.execute("select count from users where email = '{}' ".format(temp))
            records = mycursor.fetchone()
            records = records[0]
            records += 1

            mydb.reconnect()
            mycursor = mydb.cursor()
            mycursor.execute("update users set count = %s where email = %s",(records, temp ),)
            mydb.commit()
            os.remove(cwd)
            flash("Data Uploaded Successfully...")
            return redirect(url_for('main_page'))
        except mysql.connector.Error as e:
            os.remove(cwd)
            return render_template('add_records.html', msg="Some Error Occured", img_src=None)

@app.route('/display_records')
def display_records():
    if not session.get("username"):
        # if not there in the session then redirect to the login page
        return redirect(url_for("login"))
    mydb.reconnect()
    mycursor = mydb.cursor()
    mycursor.execute('select * from {}'.format(session.get('tname')))
    account = mycursor.fetchall()
    save_folder = '/static/uploads/'
    cwd = os.getcwd() + save_folder.replace("/","\|")
    cwd = cwd.replace("|","")
    for i in account:
        tempfile = str(i[0]) + ".png"
        tempfile = cwd + tempfile
        photo = i[6]
        with open(tempfile, 'wb') as file:
            file.write(photo)
    length = len(account)
    return render_template("display_records.html", account=account, length=length)


@app.route('/delete_account')
def delete_account():
    if not session.get("username"):
        # if not there in the session then redirect to the login page
        return redirect(url_for("login"))
    return render_template("delete_account.html", confirm=None)

@app.route('/confirm_delete')
def confirm_delete():
    if not session.get("username"):
        # if not there in the session then redirect to the login page
        return redirect(url_for("login"))
    code = random.randint(100000, 999999)
    session["del_code"] = code
    email = session.get('username')
    name = session.get('name')
    SUBJECT = "Verification Code To Delete Your Account"
    TEXT = "Hello "+name + ",\n\n"+ """Your Verification Code For Deleting The Smart ID Scanner Account Is \n\n """ + str(code) + """\n\nCaution!!!\nAll your saved Visiting card data will be deleted and it cannot be retrieved later\n\n\nRegards,\nSmart ID Scanner Team """
    
    sendmail(TEXT,email,SUBJECT)
    return render_template("delete_account.html", confirm=True)

@app.route('/confirm_delete', methods = ["GET", "POST"])
def confirm_delete_form():
    if request.method == "POST":
        code = request.form["code"]
        try:
            code = int(code)
            if code != session.get("del_code"):
                return render_template("delete_account.html", confirm=True, msg="Verification Code Is Incorrect!")
            
            email = session.get("username")
            name = session.get('name')
            tname = session.get("tname")
            
            mydb.reconnect()
            mycursor = mydb.cursor()
            mycursor.execute("delete from users where email = '{}'".format(email))
            mydb.commit()

            mydb.reconnect()
            mycursor = mydb.cursor()
            mycursor.execute('drop table {}'.format(tname))
            mydb.commit()

            session.pop('del_code', None)

            SUBJECT = "Account Deleted Successfully"
            TEXT = "Hello "+name + ",\n\n"+ """Your Smart ID Scanner Account has been deleted successfully... Thank you for being a valuable member. We hope to see you soon, Again!!!\n\n\nRegards,\nSmart ID Scanner Team """
            
            sendmail(TEXT,email,SUBJECT)
            
            return redirect(url_for('logout'))
        except ValueError:
            return render_template("delete_account.html",confirm=True, msg="Verification Code Cannot Contain Alphabets And Special Characters!")


@app.route('/logout')
def logout(): 
    folder = os.getcwd() + "\|" + UPLOAD_FOLDER
    folder = folder.replace("|","")
    session_folder = os.getcwd() + "\|flask_session"
    session_folder = session_folder.replace("|","")
    lst = [folder, session_folder]

    for i in lst:
        for filename in os.listdir(i):
            file_path = os.path.join(i, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('name', None)
    session.pop('tname', None)
    if session.get('del_code'):
        session.pop('del_code', None)
    if session.get('code'):
        session.pop('code', None)
    return redirect(url_for('.home'))



if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=8080)