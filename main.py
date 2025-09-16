import unicodedata
import json
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
import textwrap
from time import time
from random import Random


with open("dle_data.json", encoding = "utf-8") as f:
	data = json.load(f)

with open("events.json", encoding = "utf-8") as f:
	events = json.load(f)

with open("cruise.json", encoding = "utf-8") as f:
	cruise = json.load(f)

with open("showdown.json", encoding = "utf-8") as f:
	meta = json.load(f)

with open("research.json", encoding = "utf-8") as f:
	research = json.load(f)

try:
	with open("history.json", encoding = "utf-8") as f:
		hist = json.load(f)
except FileNotFoundError:
	hist = {}

with open("true_history.json", encoding="utf-8") as f:
		true_history = json.load(f)

def normalize_for_compare(s: str) -> str:
	# Normalize to NFKD (compatibility decomposition)
	# so "Ä" becomes "A" + "¨" and "µ" becomes "μ"
	s = unicodedata.normalize("NFKD", s)
	# Remove combining marks (accents, umlauts, etc.)
	s = "".join(c for c in s if not unicodedata.combining(c))
	# Apply case folding for Unicode-safe lowercasing
	s = s.replace("'", "").replace(".", "").replace("(", "").replace(')', '')
	return s.casefold()

def matches(a: str, b: str) -> bool:
	return normalize_for_compare(a) == normalize_for_compare(b)

def get_date(timer, event):
	if event == "No Event":
		return
	table = {
		"Research": research,
		"META Showdown": meta,
		"Cruise Missions": cruise
	}
	lookup = table.get(timer, events)
	return lookup[event]

def parse_timer(timer):
	if ':' in timer:
		return int(timer.replace(':',''))
	if timer == "Drop Only":
		return "Cannot be constructed"
	return timer

def compare_ship(solution, guess):
	result = {}

	# Simple Yes/No fields
	simple_fields = ["name", "nation", "rarity", "hull", "class", "VA"]
	for field in simple_fields:
		result[field] = "Yes" if solution[field] == guess[field] else "No"

	# Timer comparison
	sol_timer = parse_timer(solution["timer"])
	guess_timer = parse_timer(guess["timer"])
	if sol_timer == guess_timer:
		result["timer"] = "Yes"
	elif isinstance(sol_timer, str) or isinstance(guess_timer, str):
		result["timer"] = "No"
	elif sol_timer > guess_timer:
		result["timer"] = "↑"
	else:
		result["timer"] = "↓"

	# Event comparison
	sol_date = get_date(sol_timer, solution["event"])
	guess_date = get_date(guess_timer, guess["event"])
	if sol_date == guess_date:
		result["event"] = "Yes"
	elif sol_date is None or guess_date is None:
		result["event"] = "No"
	elif sol_date > guess_date:
		result["event"] = "↑"
	else:
		result["event"] = "↓"

	return result

def get_data(ship):
	if isinstance(ship, str):
		for i in names:
			if matches(i, ship):
				return data[names[i]]
	if isinstance(ship, int):
		return data.get(str(ship))

def color_bg(text, correct):
	if correct == "Yes":
		return f"\033[30;42m{text}\033[0m"  # Green bg
	if correct:
		return f"\033[97;41m{text}\033[0m"  # Red bg
	return text

def print_guess_table(guesses):
	# Column headers and widths
	headers = {"name": "Guess", "rarity": "Rarity", "hull": "Hull", "nation": "Nation", "class": "Class", "timer": "Timer", "event": "Event", "VA": "Voice Actor"}
	headerl = list(headers.keys())
	col_widths = {
		"name": 20,
		"rarity": 12,
		"hull": 4,
		"nation": 15,
		"class": 15,
		"timer": 11,
		"event": 25,
		"VA": 20
	}

	def wrap_and_center(text, width):
		"""Wrap text to a given width and center each line."""
		wrapped = textwrap.wrap(str(text), width=width) or [""]
		return [line.center(width) for line in wrapped]

	def format_row(row_data, result={}):
		"""Format a row where each cell may have multiple wrapped lines."""
		wrapped_columns = []
		for h in headers:
			r = result.get(h)
			ad = f" {r}" if r in ("↓", "↑") else ""
			t = row_data.get(h, "") + ad
			t = [color_bg(i, r) for i in wrap_and_center(t, col_widths[h])]
			wrapped_columns.append(t)
		max_lines = max(len(col) for col in wrapped_columns)


		lines = []
		for i in range(max_lines):
			line_parts = [
				wrapped_columns[j][i] if i < len(wrapped_columns[j]) else " " * col_widths[headerl[j]]
				for j in range(len(headers))
			]
			lines.append(" | ".join(line_parts))
		return "\n".join(lines)

	# Print header
	print(format_row(headers))
	print("-" * (sum(col_widths.values()) + 3 * (len(headers) - 1)))

	# Print all guesses
	for guess, res in guesses:
		print(format_row(guess, res))

names = {}
for k,v in data.items():
	names[v["name"]] = k


# def completer(text, state):
# 	n_text = normalize_for_compare(text)
# 	options = [s for s in names if normalize_for_compare(s).startswith(n_text)]
# 	if state < len(options):
# 		return options[state]
# 	else:
# 		return None

verbose = True#input("Verbose? (Y/N) ") in ("Yes", "yes", "y", "Y")

# readline.set_completer_delims(readline.get_completer_delims().replace(' ', '').replace('(','').replace(')', ''))
# readline.set_completer(completer)
# readline.parse_and_bind("tab: complete")

class NormalizingCompleter(Completer):
    """
    A prompt_toolkit Completer that matches normalized forms but shows original candidates.
    - candidates: iterable of original strings
    - show_all_on_empty: if True, pressing Tab with empty input will list all candidates
    """
    def __init__(self, candidates, show_all_on_empty=False):
        self.candidates = list(dict.fromkeys(candidates))  # remove exact duplicates while preserving order
        # precompute normalized forms
        self._cached = [(cand, normalize_for_compare(cand)) for cand in self.candidates]
        self.show_all_on_empty = show_all_on_empty

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        ntext = normalize_for_compare(text)

        # If user typed nothing and we shouldn't show everything, exit.
        if ntext == "" and not self.show_all_on_empty:
            return

        # Score and collect matches:
        # score 0 = candidate normalized startswith input (best)
        # score 1 = candidate normalized contains input
        matches = []
        for orig, norm in self._cached:
            if ntext == "":
                # if empty and we allow showing all, treat as contains match
                matches.append((1, orig))
            elif norm.startswith(ntext):
                matches.append((0, orig))
            elif ntext in norm:
                matches.append((1, orig))

        # sort matches: best matches first, then alphabetically (you can tweak)
        matches.sort(key=lambda s: (s[0], s[1].casefold()))

        # Replace entire buffer with the chosen completion
        start_pos = -len(text) if len(text) > 0 else 0

        for _, orig in matches:
            yield Completion(orig, start_position=start_pos)

def get_guess():
	completer = NormalizingCompleter(names, show_all_on_empty=False)
	user_input = prompt("Guess: ", completer=completer)
	return user_input


def get_ship_of_the_day(day, pool):
	rng = Random(day).choice(sorted(pool))
	return rng


if __name__ == "__main__":
	d = 24*3600
	today = int((time()-7*3600)//d)

	# Calculate true_history until today
	discrepancies = []
	for day in range(20309, today+1):
		day_str = str(day)
		true_ship = true_history.get(day_str)
		user_ship = hist.get(day_str)
		if true_ship is not None:
			if user_ship is not None and true_ship != user_ship:
				discrepancies.append((day_str, user_ship, true_ship))
		else:
			true_ship = get_ship_of_the_day(day, set(names)-set(hist.values()))
			if user_ship is not None and true_ship != user_ship:
				discrepancies.append((day_str, user_ship, true_ship))
				hist.pop(day_str)

	last_played = max(int(k) for k in hist) if hist else 20308

	if discrepancies:
		print(f"{len(discrepancies)} discrepancies found between your history and the true history, updating history to reflect true history!")
		# for day_str, user_ship, true_ship in discrepancies:
		# 	print(f"Day {day_str}: Your history: {user_ship} | True: {true_ship}")

	# Update history with true_history until today
	for day in range(20309, today+1):
		day_str = str(day)
		if day_str in true_history:
			hist[day_str] = true_history[day_str]

	if today == last_played:
		print("You already played today.")
		h = 24-(time()-7*3600)%d/3600
		print(f"Next game available in {int(h):0>2}h{int(h%1*60):0>2}m{int((h*3600)%60):0>2}s")
		solution = hist[str(today)]
	else:
		used = set(hist.values())
		pool = set(names)-used
		for i in range(last_played+1, today+1):
			ship = get_ship_of_the_day(i, pool)
			hist[i] = ship
			pool.remove(ship)
		solution = ship

	#print(solution)
	solution = get_data(solution)
	correct = False
	guesses = 0
	history = []
	while not correct:
		# guess = input("Guess ship: ")
		guess = get_guess()
		if guess in ("Abort", "abort"):
			print("Ending Game.")
			exit()
		gd = get_data(guess)
		if not gd:
			print("Ship not found:", guess)
			continue
		res = compare_ship(solution, gd)
		if verbose:
			history.append([gd, res])
			print_guess_table(history)
		else:
			print(f"Rarity: {res["rarity"]} | Hull Type: {res["hull"]} | Nation: {res["nation"]} | Class: {res["class"]} | Timer: {res["timer"]} | Event: {res["event"]} | VA: {res["VA"]}")
		guesses += 1
		names.pop(gd["name"])
		correct = res["name"] == "Yes"

	print("YOU WIN!")
	print(f"It took you {guesses} guesses.")

	with open("history.json", "w", encoding="utf-8") as f:
		json.dump(hist, f, indent=2)