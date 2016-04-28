import sys
import sqlite3


def slist(l):
	return ', '.join(l)

def main():
	dbfile = sys.argv[1]
	importfile = sys.argv[2]
	name = sys.argv[3]
	try:
		campaign = int(name)
	except ValueError:
		pass
	else:
		name = None

	db = sqlite3.connect(dbfile)
	c = db.cursor()

	if name:
		c.execute('INSERT INTO campaign VALUES (NULL, "%s");' % name)
		campaign = c.lastrowid
	c.execute('INSERT INTO instance VALUES (NULL, %d);' % campaign)
	instance_id = c.lastrowid

	with open(importfile, 'r') as f:
		keys = f.readline()[2:-1].split(', ')
		for line in f.readlines():
			values = line[:-1].split(', ')
			values[6] = values[6][:-1]
			c.execute('INSERT INTO snapshot (instance_id, %s) VALUES (%d, %s);' % (slist(keys), instance_id, slist(values)))

	db.commit()
	db.close()

if __name__ == '__main__':
	main()