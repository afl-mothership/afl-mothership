import json
import os
import sys

sys.path.append(os.path.dirname(exploitable_path))
gdb.execute('source %s' % exploitable_path)

#import time; time.sleep(5)
run = gdb.execute('run', to_string=True)

frames = []
try:
	frame = gdb.newest_frame()
except gdb.error:
	result = {
		'crash': False
		# TODO: store exit code from run
	}
else:
	while frame:
		frames.append(frame)
		frame = frame.older()

	# gobble some excess output
	gdb.execute('exploitable', to_string=True)
	result = {
		'crash': True,
		'exploitable': gdb.execute('exploitable', to_string=True).split('\n'),
		'pc': int(gdb.parse_and_eval('$pc')),
		'faulting instruction': gdb.execute('x/i $pc', to_string=True),
		'bt': gdb.execute('bt 50', to_string=True).split('\n')[:-1],
		'frames': [{
			'address': frame.pc(),
			'function': frame.name(),
			'filename': frame.function().symtab.fullname() if frame.function() else None,
		} for frame in frames]
	}

with open(output, 'w') as f:
	f.write(json.dumps(result))
