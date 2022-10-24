from subprocess import CalledProcessError, check_output as run
import threading
from multiprocessing import Process, Pipe, Condition
import psutil
import os
import argparse
import signal
import time
import datetime

ALPHABET_FIRST_LETTER = 'a'
ALPHABET_LAST_LETTER = 'z'
N_LETTERS = 26

g_file_name = None
g_n_physical_cores = None
g_n_threads_per_core = 1

class MainKeySearcher:
    def __init__(self, idSearcher):
        self.idSearcher = idSearcher
        self.initLetter = None
        self.endLetter = None
        self.l_partial_searchers = []

    def __str__(self):
        return f'[Process {self.idSearcher}] Search from {self.initLetter } to {self.endLetter}.'

class PartialKeySearcher:
    def __init__(self, idPartialSearcher):
        self.idPartialSearcher = idPartialSearcher
        self.initLetter = None
        self.endLetter = None

    def __str__(self):
        return f'[Thread {self.idPartialSearcher}] Search from {self.initLetter } to {self.endLetter}.'

############################### ARGUMENTS MANAGEMENT ###############################
def parseArguments():

    args = getArguments()

    setFile(args.file)

    setCoresAndThreads(args.cores, args.multithreading)

    print(f"Starting to brute force file {g_file_name} with {g_n_physical_cores*g_n_threads_per_core} search cores({g_n_physical_cores} cores x {g_n_threads_per_core} threads).")

def getArguments():
    parser = argparse.ArgumentParser(description="Brute force a gpg file key.")
    parser.add_argument('--file', type=lambda x: isValidFile(parser, x), required=True, help="GPG file you want to brute force.")
    parser.add_argument('--cores', type=lambda x: isValidNumberCores(parser, x), help="Number of physical cores you want to use. Deafult is all available.")
    parser.add_argument('--multithreading', default=True, action='store_true' , help="Use multithreading if possible. Activated by default.")
    parser.add_argument('--no-multithreading', dest='multithreading', action='store_false', help="Do NOT use multithreading.")

    return parser.parse_args()

def isValidFile(parser, file):
    if not os.path.exists(file):
        parser.error(f"The file '{file}' does not exists.")
    if not os.path.isfile(file):
        parser.error(f"The argument '{file}' is not a file.")
    if not file.endswith(".gpg"):
        parser.error(f"The file '{file}' is not a gpg file.")

    return file 

def isValidNumberCores(parser, n_cores):
    n_real_cores = psutil.cpu_count(logical=False)
    if int(n_cores) <= 0:
        parser.error(f"The number of cores must be higher than 0.")
    if n_real_cores < int(n_cores):
        parser.error(f"Number of cores invalid. You computer has {n_real_cores} physical cores and you gave {n_cores}.")
    else:
        return int(n_cores)

def setFile(args_file):
    global g_file_name 
    g_file_name = args_file

def setCoresAndThreads(args_core, args_is_multithreading):
    global g_n_physical_cores
    global g_n_threads_per_core
    
    if args_core != None:
        g_n_physical_cores = args_core
    else:
        g_n_physical_cores = psutil.cpu_count(logical=False)

    if args_is_multithreading:
        n_logical_cores = psutil.cpu_count()
        g_n_threads_per_core = int(n_logical_cores / psutil.cpu_count(logical=False))
    else:
        g_n_threads_per_core = 1


############################### SIGNALS MANAGEMENT ###############################
def sigint_handler(signum, frame, l_main_searchers):

    terminateMainSearchers(l_main_searchers)

    print("Key Search aborted manually.")
    exit(1)


############################### MAIN SEARCHERS MANAGEMENT ###############################
def createMainSearchers(l_main_searchers, pipe_send):
    global g_n_physical_cores 
    n_main_searchers = g_n_physical_cores

    for main_searcher_id in range(0, n_main_searchers):
        
        main_searcher = MainKeySearcher(main_searcher_id)

        getLettersPerMainKeySearcher(main_searcher, n_main_searchers)

        main_searcher_process = Process(target=mainSearchKey,
                                        args=(main_searcher,
                                              pipe_send,
                                             )
                                       )

        l_main_searchers.append(main_searcher_process)

def getLettersPerMainKeySearcher(main_searcher, n_main_searchers):
    letters_per_main = round(N_LETTERS / n_main_searchers)

    main_searcher.initLetter = chr( ord(ALPHABET_FIRST_LETTER) + letters_per_main * main_searcher.idSearcher )
    main_searcher.endLetter = chr( ( ord(main_searcher.initLetter) + letters_per_main ) - 1 )

    if main_searcher.endLetter > ALPHABET_LAST_LETTER or (main_searcher.idSearcher == (n_main_searchers-1) and main_searcher.endLetter < ALPHABET_LAST_LETTER):
        main_searcher.endLetter = ALPHABET_LAST_LETTER

def mainSearchKey(main_searcher, pipe_send):
    cond_key_found = Condition()
    key_found = []

    createPartialSearcher(main_searcher.l_partial_searchers,
                          main_searcher.initLetter,
                          main_searcher.endLetter,
                          main_searcher.idSearcher,
                          cond_key_found,
                          key_found
                         )

    startSearchers(main_searcher.l_partial_searchers)

    getKey(pipe_send, cond_key_found, key_found)

    joinPartialSearchers(main_searcher.l_partial_searchers)


############################### PARTIAL SEARCHERS MANAGEMENT ###############################
def createPartialSearcher(l_partial_searchers, main_init_letter, main_end_letter, main_searcher_id, cond_key_found, key_found):
    global g_n_threads_per_core
    n_partial_searchers = g_n_threads_per_core

    for partial_searcher_id in range(0, n_partial_searchers):

        partial_searcher = PartialKeySearcher(partial_searcher_id)

        getLettersPerPartialSearchKey(partial_searcher, main_init_letter, main_end_letter)

        partial_searcher_thread = threading.Thread(target=partialSearchKey,
                                                   args=(partial_searcher,
                                                         main_searcher_id,
                                                         cond_key_found,
                                                         key_found
                                                        )

                                                  )

        l_partial_searchers.append(partial_searcher_thread)

def getLettersPerPartialSearchKey(partial_searcher, main_searcher_init_letter, main_searcher_end_letter):
    global g_n_threads_per_core
    n_partial_searchers = g_n_threads_per_core
    
    n_letters = ( ord(main_searcher_end_letter) - ord(main_searcher_init_letter) ) + 1
    letters_per_partial = round(n_letters / n_partial_searchers)

    partial_searcher.initLetter = chr( ord(main_searcher_init_letter) + letters_per_partial * partial_searcher.idPartialSearcher )
    partial_searcher.endLetter = chr( ( ord(partial_searcher.initLetter) + letters_per_partial ) - 1 )

    if partial_searcher.endLetter > main_searcher_end_letter or (partial_searcher.idPartialSearcher == (n_partial_searchers-1)and partial_searcher.endLetter < main_searcher_end_letter):
        partial_searcher.endLetter = main_searcher_end_letter

def partialSearchKey(partial_searcher, main_searcher_id, cond_key_found, key_found):

    key_found.append(searchKey(partial_searcher, main_searcher_id))

    with cond_key_found:
        cond_key_found.notify()


############################### KEY MANAGEMENT ###############################
def searchKey(partial_searcher_key, main_searcher_id):
    key = []
    key.append(partial_searcher_key.initLetter)
    while 1:
        key_string = array2String(key)

        print("[Process " + str(main_searcher_id) + "::Thread " + str(partial_searcher_key.idPartialSearcher) + "] Tried: " + key_string)
        if tryKey(key_string) == 1:
            return key_string

        key = nextKey(key, partial_searcher_key)

def array2String(key):
    key_string = ''
    for c in key:
        key_string += c

    return key_string

def tryKey(key):
    try:
        command = "gpg --pinentry-mode loopback --passphrase " + key + " -d " + g_file_name + " 2>&1"
        output = run(command, shell=True)
    except CalledProcessError:
        print("Wrong")
        return 0

    try:
        os.mkdir('keys_found')
    except OSError:
        pass

    command = "echo " + key + " >  keys_found/" + g_file_name.split('/')[-1].split('.')[0] + "_key.txt"
    run(command, shell=True)

    return 1

def nextKey(key, partial_searcher_key):
    index = -1

    for char in key:
        if -index == len(key):
            if key[index] == partial_searcher_key.endLetter:
                key[index] = partial_searcher_key.initLetter
                key += ALPHABET_FIRST_LETTER
                return key

            else:
                key[index] = chr( ord(key[index]) + 1 )
                return key

        else:
            if key[index] == ALPHABET_LAST_LETTER:
                key[index] = ALPHABET_FIRST_LETTER
                index += -1

            else:
                key[index] = chr( ord(key[index]) + 1 )
                return key

def getKey(pipe_send, cond_key_found, key_found):
    with cond_key_found:
        cond_key_found.wait()
        pipe_send.send(key_found[0])


############################### PROCESSES AND THREADS MANAGEMENT ###############################

def startSearchers(l_searchers):
    for searcher in l_searchers:
        searcher.start()

def joinPartialSearchers(l_partial_searchers):
    for partial_searcher in l_partial_searchers:
        partial_searcher.join()

def terminateMainSearchers(l_main_searchers):
    for main_searcher in l_main_searchers:
        main_searcher.terminate()


def main():
    parseArguments()

    pipe_recv, pipe_send = Pipe()
    l_main_searchers = []

    signal.signal(signal.SIGINT, lambda signum, frame: sigint_handler(signum, frame, l_main_searchers))

    createMainSearchers(l_main_searchers, pipe_send)

    start_time = time.time()
    startSearchers(l_main_searchers)
    
    key_found = pipe_recv.recv()
    end_time = time.time()

    terminateMainSearchers(l_main_searchers)

    print(f'The key has been found: {key_found}.')
    print(f'Time needed: {datetime.timedelta(seconds=end_time - start_time)}.')


if __name__ == '__main__': 
    main()
    