import sys
import time
import http.client
import json
import smtplib
import configparser
from string import Template
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

RETRY_DELAY_MINUTES = 10

def load_json(filename):
    with open(filename, 'r') as json_file:
        return json.load(json_file)

def save_json(filename, data):
    for user in data:
        user.pop('done', None)
        for fund in user['funds']:
            fund.pop('done', None)
            fund['previous_date'] = fund.pop('new_date', None)
            fund['previous_value'] = fund.pop('new_value', None)
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
    total_value = 0.0
    for fund in data['funds']:
        fund_template = Template(get_template("fund"))
        daily_change = get_change(fund['previous_value'], fund['new_value'])
        value = get_investment_value(fund['new_value'], fund['holdings'])
        total_value += value
        funds += fund_template.substitute(fund_name=fund['name'], daily_change=format_percentage(daily_change), value=format_money(value))
    current_cash = data['current_cash']
    fees = get_total_fees_paid(data['cash_payments'], data['current_cash'])
    grand_total = current_cash + total_value
    total_payment = sum(data['cash_payments']) + sum(data['investment_payments'])
    total_profitloss = grand_total - total_payment
    email = email_template.substitute(date=data['funds'][0]['new_date'], funds=funds, cash=format_money(current_cash), fees=format_money(fees), total_investment=format_money(total_value), grand_total=format_money(grand_total), total_payment=format_money(total_payment), profit_or_loss=str_profit_or_loss(total_profitloss), total_profitloss=format_money(total_profitloss), overall_change=format_percentage(get_change(total_payment, grand_total)))
    return email

def format_money(value):
    return '{0:.2f}'.format(value)

def format_percentage(value):
    return '{0:+.2f'.format(value)

def str_profit_or_loss(value):
    if value > 0:
        return "profit"
    else:
        return "loss"

def get_change(prev, curr):
    return (1 - prev / curr) * 100

def get_investment_value(price, holdings):
    return price / 100 * holdings

def get_total_fees_paid(cash_payments, current_cash):
    return sum(cash_payments) - current_cash

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
        if data['previous_date'] != data['new_date']:
            data['new_value'] = float(latest_close_row.select_one("td.text").get_text()[4:])
            return True
    return False

if __name__ == "__main__":
    finished = False
    data = load_json('data.json')
    while not finished:
        for user in data:
            if not 'done' in user:
                user['done'] = False
            if not user['done']:
                for fund in user['funds']:
                    if not 'done' in fund:
                        fund['done'] = False
                    if not fund['done'] and get_data_from_morningstar_page(fund):
                        fund['done'] = True
                if all(fund['done'] for fund in user['funds']):
                    send_email(make_email(user))
                    user['done'] = True
        if all(user['done'] for user in data):
            finished = True
    #save_json('previous_data_test.json', data)
