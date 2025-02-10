import ast
import os
import json
from flask import Flask, render_template, request, redirect, session, url_for, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import re
import pyterrier as pt
from logging.handlers import RotatingFileHandler
import logging.handlers

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Path for development envoriment
sushi_files_path = "/home/ubuntu/sushi-files"
index_path_tof = "/home/ubuntu/terrierindex/tof/data.properties"
index_path_to = "/home/ubuntu/terrierindex/to/data.properties"
index_path_tf = "/home/ubuntu/terrierindex/tf/data.properties"
index_path_of = "/home/ubuntu/terrierindex/of/data.properties"
index_path_t = "/home/ubuntu/terrierindex/t/data.properties"
index_path_o = "/home/ubuntu/terrierindex/o/data.properties"
index_path_f = "/home/ubuntu/terrierindex/f/data.properties"

# sushi_files_path = "/mnt/sushi-files"
# index_path_tof = "/mnt/terrierindex/tof/data.properties"
# index_path_to = "/mnt/terrierindex/to/data.properties"
# index_path_tf = "/mnt/terrierindex/tf/data.properties"
# index_path_of = "/mnt/terrierindex/of/data.properties"
# index_path_t = "/mnt/terrierindex/t/data.properties"
# index_path_o = "/mnt/terrierindex/o/data.properties"
# index_path_f = "/mnt/terrierindex/f/data.properties"

# Setting for log
log_file_path = os.path.join(os.path.dirname(__file__), 'logs', 'log.txt')
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger()


# Initializing Database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            password TEXT NOT NULL)
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            topic_num TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS session (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            topic_id INTEGER,
            query TEXT,
            document_id INTEGER,
            file TEXT,
            folder TEXT,
            box TEXT,
            title TEXT,
            folderlabel TEXT,
            rank INTEGER,
            path TEXT,
            relevance INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(topic_id) REFERENCES topics(topic_id)
        )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS official_topics (
    id TEXT
    title TEXT,
    dev_topicum TEXT
    )
    ''')
    conn.commit()
    conn.close()


def get_db():
    """Connect to the database, or create one if it doesn't exist."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('database.db')
    return db


def get_dev_db():
    """Connect to the database, or create one if it doesn't exist."""
    db = getattr(g, '_database', None)
    print("DEV Database")
    if db is None:
        db = g._database = sqlite3.connect('database-topic_dev.db')
    return db


def make_dict_file_path(indir):
    d_file_path = {}
    for sd1 in os.listdir(indir):
        if re.match('^\.', sd1):
            continue

        for sd2 in os.listdir(os.path.join(indir, sd1)):
            if re.match('^\.', sd2):
                continue

            for f in os.listdir(os.path.join(indir, sd1, sd2)):
                if re.match('^\.', f):
                    continue

                d_file_path[f] = os.path.join("sushi-files", sd1, sd2, f)

    return d_file_path


def load_sushi_index(index_path):
    if not pt.started():
        pt.init()

    indexref = pt.IndexRef.of(index_path)
    index = pt.IndexFactory.of(indexref)

    BM25 = pt.BatchRetrieve(index, wmodel="BM25", metadata=['docno', 'folder', 'box', 'title', 'folderlabel'],
                            num_results=100)
    # sdm = pt.rewrite.SequentialDependence(remove_stopwords=True)
    # SDMBM25 = sdm >> BM25
    return BM25


def terrier_search(query, engine):
    if not pt.started(): pt.init()
    query = re.sub(r'[^a-zA-Z0-9\s]', '', query)  # Terries fails if punctuation is found in a query
    result = engine.search(query)

    rankedList = result['docno']
    rankedList.drop_duplicates(inplace=True)

    # return rankedList.tolist()
    return result


    # dict_pdf_path = make_dict_file_path("/home/Documents/sushi-a/sushi-files")
dict_pdf_path = make_dict_file_path(sushi_files_path)


# Function to get relevance by file name
def get_relevance_from_json(file_name):
    user_name = session.get('user_name')
    topic_id = session.get('topic_id')
    topic = session.get('topic')
    is_new = session['topic_is_new']
    # Iterate over the list of dictionaries
    json_filename = f"{user_name}_{topic}_{topic_id}.json"
    json_path = os.path.join('relevance_data', json_filename)

    if not os.path.exists(json_path):
        flash("Relevance document not present for this topic, kindly create a new topic", "error")
    else:
        with open(json_path, 'r') as file:
            relevance_doc = json.load(file)
        for item in relevance_doc:
            if item['file'] == file_name:
                return item['relevance']
        return None  # If file_name doesn't match any entry


@app.route('/', methods=['GET', 'POST'])
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def user_login():
    username = request.form['username']
    password = request.form['password']

    db = get_db()
    cursor = db.execute('SELECT * FROM users WHERE user_name = ?', (username,))
    user = cursor.fetchone()

    if not user:
        flash('User does not exist', 'error')
        return redirect(url_for('home'))

    session['logged_in'] = True
    session['user_id'] = user[0]
    session['user_name'] = user[1]

    if user and check_password_hash(user[2], password):
        app.logger.info('LOGIN ' + username)
        # return redirect(url_for('create_topic'))
        return redirect(url_for('select_topic'))
    else:
        flash('Invalid username or password', 'danger')
        return redirect(url_for('home'))


@app.route('/register', methods=['GET'])
def register_page():
    return render_template('create_user.html')


@app.route('/result')
def result():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    selected_dataset = session.get('selected_dataset')

    return render_template('result.html', selected_dataset=selected_dataset)


@app.route('/user_registration', methods=['POST'])
def register():
    """Handle user registration, hash password, and save to the database."""
    username = request.form['username']
    password = request.form['password']
    hashed_password = generate_password_hash(password)

    db = get_db()
    try:
        # Insert new user with hashed password
        db.execute('INSERT INTO users (user_name, password) VALUES (?, ?)', (username, hashed_password))
        flash('User registered successfully!', 'success')
        db.commit()

        app.logger.info('REGISTER ' + username)

        return redirect(url_for('login'))
    except sqlite3.IntegrityError:
        # Handle duplicate username
        flash('Username already exists. Please choose a different one.', 'danger')
        return redirect(url_for('register_page'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# Page for creating a topic
@app.route('/create_topic', methods=['GET'])
def create_topic():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_id = session["user_id"]
    db = get_db()
    rows = db.execute('SELECT t.topic_id, t.topic_num FROM topics t where t.user_id = ?', (user_id,))
    topics = [{'id': row[0], 'name': row[1]} for row in rows.fetchall()]  # Fetch topic names
    return render_template('create_topic.html', topics=topics)


# Page for creating a topic
@app.route('/select_topic', methods=['GET'])
def select_topic():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_id = session["user_id"]

    db = get_db()
    rows = db.execute('SELECT d.id, d.title FROM official_topics d')
    topics = [{'id': row[0], 'text': row[1]} for row in rows.fetchall()]

    return render_template('select_topic.html', topics=topics)


# POST handler for creating a topic
@app.route('/create_topic', methods=['POST'])
def handle_create_topic():
    user_id = session['user_id']
    user_name = session.get('user_name')

    existing_topic_str = request.form.get('existing_topic')
    new_topic_str = request.form.get('new_topic').strip() if request.form.get('new_topic') else None

    # Backend validation: ensure only one of existing_topic or new_topic is filled
    if (existing_topic_str and new_topic_str) or (not existing_topic_str and not new_topic_str):
        flash("Please either select an existing topic or enter a new topic, not both.", "error")
        return redirect(url_for('create_topic'))

    if existing_topic_str:
        flash('existing_topic')
        existing_topic = ast.literal_eval(existing_topic_str)
        session['topic_is_new'] = False
        session['topic_id'] = existing_topic['id']
        session['topic'] = existing_topic['name']
    elif new_topic_str:
        db = get_db()

        # Creating a topic
        db.execute('INSERT INTO topics (user_id, topic_num) VALUES (?, ?)', (user_id, new_topic_str))
        row = db.execute('SELECT topic_id FROM topics t WHERE t.user_id = ? AND t.topic_num = ?',
                         (user_id, new_topic_str))
        db.commit()

        session['topic_is_new'] = True
        session['topic_id'] = row.fetchone()[0]
        session['topic'] = new_topic_str

    app.logger.info('TOPIC ' + user_name + ' TOPIC_NUM ' + session['topic'])
    # Storing session
    return redirect(url_for('search'))


# POST handler for selecting a topic
@app.route('/select_topic', methods=['POST'])
def handle_select_topic():
    user_id = session['user_id']
    user_name = session.get('user_name')

    existing_topic_str = request.form.get('existing_topic')

    # Backend validation: ensure only one of existing_topic or new_topic is filled
    if not existing_topic_str:
        flash("Please either select an existing topic.", "error")
        return redirect(url_for('select_topic'))

    if existing_topic_str:
        flash('existing_topic')
        existing_topic = ast.literal_eval(existing_topic_str)
        session['topic_is_new'] = False
        session['topic_id'] = existing_topic['id']
        session['topic'] = existing_topic['text']

    app.logger.info('TOPIC ' + user_name + ' TOPIC_NUM ' + session['topic'])
    # Storing session
    return redirect(url_for('search'))


# Page for search
@app.route('/search', methods=['GET'])
def search():
    user_name = session.get('user_name')
    topic_id = session.get('topic_id')
    topic = session.get('topic')
    is_new = session['topic_is_new']
    query = None

    selected_dataset = session.get('selected_dataset')

    # if user_name and topic:
    #     if is_new:
    #         return render_template('result.html', user_name=user_name, topic=topic)
    #     else:
    #         json_filename = f"{user_name}_{topic}_{topic_id}.json"
    #         json_path = os.path.join('relevance_data', json_filename)

    #         if not os.path.exists(json_path):
    #             flash("Topic created, no relevance data present", "error")
    #         else:
    #             with open(json_path, 'r') as file:
    #                 relevance_doc = json.load(file)
    #             query = relevance_doc[0]["query"]
    #             print(query)

    # app.logger.info('SEARCH ' + user_name + ' TOPIC_NUM ' + session['topic'] + ' QUERY ' + query)

    return render_template('result.html', user_name=user_name, topic=topic, query=query,
                           selected_dataset=selected_dataset)

    # return redirect(url_for('select_topic'))


# POST handler for search
@app.route('/search', methods=['POST'])
def handle_search():
    is_new = session['topic_is_new']
    user_name = session.get('user_name')
    query = request.form['query']
    user_id = session['user_id']
    topic_id = session['topic_id']
    dataset = request.form['dataset']  # Get selected dataset

    session['selected_dataset'] = dataset

    db = get_db()

    # Search depending on selected dataset
    if dataset == 'tof':
        # sushi_index = load_sushi_index("/home/Documents/sushi-a/terrierindex/tof/data.properties")
        sushi_index = load_sushi_index(index_path_tof)

    elif dataset == 'to':
        sushi_index = load_sushi_index(index_path_to)

    elif dataset == 'tf':
        sushi_index = load_sushi_index(index_path_tf)

    elif dataset == 'of':
        sushi_index = load_sushi_index(index_path_of)

    elif dataset == 't':
        sushi_index = load_sushi_index(index_path_t)

    elif dataset == 'o':
        sushi_index = load_sushi_index(index_path_o)

    elif dataset == 'f':
        sushi_index = load_sushi_index(index_path_f)

    # print("INDEX USING: " + sushi_index)
    terrier_results = terrier_search(query, sushi_index)
    results = terrier_results.to_dict(orient='records')

    resn = []

    for doc in results:
        print("DEBUG" + str(doc['docid']))
        global dict_pdf_path
        file_path = dict_pdf_path[doc['docno']]
        doc['path'] = file_path

        user_id = session.get('user_id')
        topic_id = session.get('topic_id')

        # get relevance from the database
        # connect to db
        conn = get_db()
        c = db.cursor()

        c.execute('''
        SELECT relevance
        FROM session
        WHERE file = ? AND user_id = ? AND topic_id = ?
        ''', (doc['docno'], user_id, topic_id))

        result = c.fetchone()

        if result:
            relevance_val = result[0]
        else:
            relevance_val = 0

        doc['relevance'] = relevance_val

        resn.append(doc)

        # Insert an entry to session table
        db.execute('''
        INSERT INTO session (user_id, topic_id, query, document_id, file, folder, box, title, folderlabel, rank, path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, topic_id, query, doc['docid'], doc['docno'], doc['folder'], doc['box'], doc['title'],
              doc['folderlabel'], doc['rank'], file_path))

    db.commit()

    app.logger.info('SEARCH ' + user_name + ' TOPIC_NUM ' + session['topic'] + ' QUERY ' + query + ' FIELD ' + dataset)

    return render_template('result.html', results=resn, query=query, user_name=session['user_name'],
                           topic=session['topic'], selected_dataset=dataset)


@app.route('/load_results', methods=['POST'])
def load_results():
    is_new = session['topic_is_new']
    user_name = session.get('user_name')
    # query = request.form['query']
    query = "DEV"
    user_id = session['user_id']
    topic_id = session['topic_id']
    # dataset = request.form['dataset']  # Get selected dataset
    dataset = 'tof'

    session['selected_dataset'] = dataset

    db = get_db()

    c = db.cursor()

    # WORKING
    row = c.execute("SELECT dev_topic_num FROM official_topics WHERE id = ?", (topic_id,))
    topic_num = row.fetchone()[0]
    print(topic_num)

    row = c.execute("SELECT topic_id FROM topics WHERE topic_num = ?", (topic_num,))
    dev_topic_id = row.fetchone()[0]
    c.close()

    devb = sqlite3.connect('database-topic_dev.db')
    c = devb.cursor()
    print(devb)
    row = c.execute("SELECT user_id FROM topics WHERE topic_id = ?", (dev_topic_id,))
    ui = row.fetchone()[0]

    print("TopicID, UserID ", dev_topic_id, ui)
    c.close()

    cn = devb.cursor()

    cn.execute("""
    SELECT *
    FROM session
    WHERE session_id IN (
        SELECT MAX(session_id)
        FROM session
        WHERE topic_id= ? AND user_id = ? AND NOT relevance = 0
        GROUP BY document_id
    )
    """, (dev_topic_id, ui,))

    results = cn.fetchall()

    print("Nyanchi")
    print(results)

    # results = rows.fetchall()
    # print(results)
    resn = []

    for r in results:
        query = r[3]
        doc_id = r[4]
        file_name = r[5]
        folder = r[6]
        box = r[7]
        title = r[8]
        folder_label = r[9]
        rank = r[10]
        file_path = r[11]
        # relevance_val = r[12]
        relevance_val = 0

        doc = {}
        doc['rank'] = rank
        doc['folder'] = folder
        doc['title'] = title
        doc['box'] = box
        doc['folderlabel'] = folder_label
        doc['docno'] = file_name
        doc['id'] = doc_id
        doc['relevance'] = relevance_val
        doc['path'] = file_path

        resn.append(doc)

        # Insert an entry to session table
        db.execute('''
        INSERT INTO session (user_id, topic_id, query, document_id, file, folder, box, title, folderlabel, rank, path, relevance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
        user_id, topic_id, query, doc_id, file_name, folder, box, title, folder_label, rank, file_path, relevance_val))

        db.commit()

    app.logger.info('SEARCH ' + user_name + ' TOPIC_NUM ' + session['topic'] + ' QUERY ' + query + ' FIELD ' + dataset)

    return render_template('result.html', results=resn, query=query, user_name=session['user_name'],
                           topic=session['topic'], selected_dataset=dataset)


# Update Relevance Judgement
@app.route('/update_relevance', methods=['POST'])
def update_relevance():
    document_id = request.form['document_id']
    user_name = session.get('user_name')
    file_name = request.form['file_name']
    relevance = request.form['relevance']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # print("DEBUGGING:" + " " + file_name + " " + document_id)

    # Update relevance
    c.execute('''
        UPDATE session
        SET relevance = ?
        WHERE file = ? AND user_id = ? AND topic_id = ?
    ''', (relevance, file_name, session['user_id'], session['topic_id']))

    conn.commit()
    conn.close()

    app.logger.info('UPDATE_RELEVANCE ' + user_name + ' TOPIC_NUM ' + session[
        'topic'] + ' FILE ' + file_name + ' RELEVANCE ' + relevance)

    return '', 204  # Return nothing when success


# Submit Relevance Judgement
@app.route('/submit_relevance', methods=['POST'])
def submit_relevance():
    user_id = session['user_id']
    topic_id = session['topic_id']
    user_name = session['user_name']
    topic_num = session['topic']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    print("DEBUGGING:" + str(user_id) + topic_id + user_name + topic_num)

    # c.execute('''
    #    SELECT s.query, s.file, s.relevance, u.user_name, t.title, t.dev_topic_num
    #    FROM session s
    #    JOIN users u ON s.user_id = u.user_id
    #    JOIN official_topics t ON s.topic_id = t.id
    #    WHERE s.user_id = ? AND s.topic_id = ? AND s.relevance != 0
    # ''', (user_id, topic_id))

    c.execute('''
    SELECT s.query, s.file, s.relevance, u.user_name, t.title, t.dev_topic_num
    FROM session s
    JOIN users u ON s.user_id = u.user_id
    JOIN official_topics t ON s.topic_id = t.id
    WHERE s.session_id IN (
        SELECT MAX(session_id)
        FROM session
        WHERE user_id = ? AND topic_id = ? AND relevance != 0
        GROUP BY document_id
    )
    ''', (user_id, topic_id))

    rows = c.fetchall()
    conn.close()

    # print("DEBUGGING:" + " " + rows)

    # Converteing to JSON
    relevance_data = []
    for row in rows:
        relevance_data.append({
            'query': row[0],
            'file': row[1],
            'relevance': row[2],
            'user_name': row[3],
            'title': row[4],
            'dev_topic_num': row[5],
        })

    # Creating output file name 
    json_filename = f"{user_name}_{topic_num}_{session['topic_id']}.json"
    json_path = os.path.join('relevance_data', json_filename)

    # in the case there is no relevance_data folder
    os.makedirs('relevance_data', exist_ok=True)

    # Storing JSON file
    with open(json_path, 'w') as f:
        json.dump(relevance_data, f, indent=4)

    app.logger.info('SUBMIT_RELEVANCE ' + user_name + ' TOPIC_NUM ' + session['topic'] + ' RELFILE ' + json_filename)

    return redirect(url_for('end_topic'))


# Page foer finishing topic
@app.route('/end_topic')
def end_topic():
    return render_template('end_topic.html', topic_id=session['topic_id'], topic=session['topic'])


# Enfpoint for PDF viwer 
@app.route('/view_pdf/<path:pdf_path>')
def view_pdf(pdf_path):
    return render_template('pdf_viewer.html', pdf_path=pdf_path)


if __name__ == '__main__':
    init_db()
    pt.java.set_java_home("/home/ubuntu/search-demo/jdk-22.0.2/lib/")
    # app.run(host="0.0.0.0", port=8889, debug=True)
    app.run(host="0.0.0.0", port=5000, debug=True)