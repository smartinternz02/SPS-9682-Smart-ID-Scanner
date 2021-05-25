import smtplib
import os

s = smtplib.SMTP('smtp.gmail.com', 587)

def sendmail(TEXT,email,SUBJECT):
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login("naikvinay890@gmail.com", "srushti1@")
    message  = 'Subject: {}\n\n{}'.format(SUBJECT, TEXT)
    s.sendmail("naikvinay890@gmail.com", email, message)
    s.quit()

    

