import sys
import time
import http.client
import json
import smtplib
import configparser
from premailer import transform
from string import Template
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

RETRY_DELAY_MINUTES = 10

def load_json(filename):
    with open(filename, 'r') as json_file:
        return json.load(json_file)

def save_json(filename, data):
    for fund in data:
        fund.pop('done', None)
        fund['latest_date'] = fund.pop('new_date', None)
        fund['latest_value'] = fund.pop('new_value', None)
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)

def send_email(body):
    config = configparser.ConfigParser()
    config.read('email.cfg')
    config = config['email']
    msg = MIMEText(body, 'html')
    msg['Subject'] = "Test Subject"
    msg['From'] = config['address']
    msg['To'] = config['address']
    srv = smtplib.SMTP(config['server'], int(config['port']))
    if config['secure'].lower() == "true":
        srv.starttls()
    srv.login(config['address'], config['password'])
    srv.send_message(msg)

def get_template(name):
    with open(name + "_template.html") as f:
        return f.read()

def make_email(data):
    email_template = Template(get_template("email"))
    funds = ""
    for fund in data:
        fund_template = Template(get_template("fund"))
        daily_change = get_daily_change(fund['latest_value'], fund['new_value'])
        value = get_investment_value(fund['new_value'], fund['holdings'])
        change_class = "positive" if daily_change > 0 else "negative"
        funds += fund_template.substitute(fund_name=fund['name'], daily_change='{0:+.2f}'.format(daily_change), value='{0:.2f}'.format(value), change_class=change_class)
    email = email_template.substitute(date=data[0]['new_date'], funds=funds)
    return transform(email)

def get_daily_change(prev, curr):
    return (1 - prev / curr) * 100

def get_investment_value(price, holdings):
    return price / 100 * holdings

def get_morningstar_page(id):
    conn = http.client.HTTPConnection("www.morningstar.co.uk")
    conn.request("GET", "/uk/funds/snapshot/snapshot.aspx?id=" + id) 
    response = conn.getresponse()
    html = response.read()
    conn.close()
    return html

def get_data_from_morningstar_page(data):
    html = get_morningstar_page(data['morningstar_id'])
    soup = BeautifulSoup(html, 'html.parser')
    latest_close_row = soup.select_one("#overviewQuickstatsDiv tr:nth-of-type(2)")
    if (latest_close_row is not None):
        data['new_date'] = latest_close_row.select_one("span.heading").get_text()
        if data['latest_date'] != data['new_date']:
            data['new_value'] = float(latest_close_row.select_one("td.text").get_text()[4:])
            return True
    return False

def inform(data):
    pass

if __name__ == "__main__":
    finished = False
    data = load_json('previous_data_test.json')
    while not finished:
        for fund in data:
            if not 'done' in fund:
                fund['done'] = False
            if not fund['done'] and get_data_from_morningstar_page(fund):
                fund['done'] = True
        if all(fund['done'] for fund in data):
            finished = True
    #save_json('previous_data_test.json', data)
    send_email(make_email(data))
