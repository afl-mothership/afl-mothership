import sys
import sqlite3

def main():
	db = sqlite3.connect(sys.argv[1])
	c = db.cursor()

	for instance, start, last_update, last_path, last_crash, last_hang in list(c.execute('SELECT id, start_time, last_update, last_path, last_crash, last_hang FROM instance')):
		c.execute('UPDATE instance SET start_time=?, last_update=?, last_path=?, last_crash=?, last_hang=? WHERE id=?', (
			0,
			last_update - start,
			last_path - start,
			last_crash - start,
			last_hang - start,

			instance
		))

		for crash, created in list(c.execute('SELECT id, created FROM crash WHERE instance_id = ?', (instance,))):
			c.execute('UPDATE crash SET created = ? WHERE id = ?', (created - start, crash))

		for snapshot, unix_time in list(c.execute('SELECT id, unix_time FROM snapshot WHERE instance_id = ?', (instance,))):
			c.execute('UPDATE snapshot SET unix_time = ? WHERE id = ?', (unix_time - start, snapshot))

	db.commit()


if __name__ == '__main__':
	main()