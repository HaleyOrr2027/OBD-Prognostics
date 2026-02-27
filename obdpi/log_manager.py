import logging # Built-in Python tool for writing logs
import os #Lets you interact with your computer
import glob
from datetime import datetime #Used to get the current time for naming files.


class LogManager: # Creating blueprint for something called LogManager

    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    LOGS_DIR = os.path.join(BASE_DIR, 'logs/') # builds files path for logs in base dir

    def __init__(self, log_file_path_sub=''): # Constructor
        self.full_log_file_path = os.path.join(self.LOGS_DIR, log_file_path_sub)
        if not os.path.exists(self.full_log_file_path):  #If the given path doesn't exist, make it. 
            os.makedirs(self.full_log_file_path)
        if self.get_log_count() > 10: # get_log_count is function in the class
            self.delete_log_file_by_name(self.get_oldest_log_file_name()) #Keep only last 10 logs, delete oldest
        self.log_file_name = self.full_log_file_path + self.get_timestamp_string() + '.log' #Create log files with their timestamp as names
        logging.basicConfig(filename=self.log_file_name, level=logging.DEBUG, format='%(asctime)s: %(message)s') #Set up logging with these rules: 

    def add_info_entry_to_log(self, info_text):
        logging.info(str(info_text))

    def add_debug_entry_to_log(self, debug_text):
        logging.debug(str(debug_text))

    def add_warning_entry_to_log(self, warning_text):
        logging.warning(str(warning_text))

    def get_timestamp_string(self):
        return str(datetime.now().strftime('%Y%m%d_%H%M%S'))

    def get_log_count(self):
        return len([f for f in os.listdir(self.full_log_file_path) if os.path.isfile(os.path.join(self.full_log_file_path, f))])
    # os.listdir(...) gives everything inside a given folder.
    # The list here of the path strings is created temporarily, then discarded after lens in done. 

    def get_oldest_log_file_name(self):
        all_log_files = glob.glob(self.full_log_file_path + '*.log')
        # glob is a module for pattern matching filenames.
        # *.log means  "Any filename that ends in .log"
        # glob.glob(...) Returns a LIST of all matching files as full paths. 
        all_log_files.sort(key=os.path.getmtime)
        # .sort rearranges alphabetically.
        # key= allows to sort by a certain criteria - here it's the last modified time of a file
        oldest_log_file_name = os.path.basename(all_log_files[0])
        return oldest_log_file_name

    def delete_log_file_by_name(self, log_file_name):
        if os.path.exists(self.full_log_file_path + log_file_name):
            os.remove(self.full_log_file_path + log_file_name)

    def log_event_decorator(self, event_name, event_type):
        # “Create a decorator configured for this specific event.”
        def decorator(func):
            # Receives the function we are decorating
            def func_wrapper(*args, **kwargs):
                # what actually runs when the decorated function is called
                result = func(*args, **kwargs)
                output = str(event_name) + ": " + str(result)
                if str(event_type) == "INFO":
                    self.add_info_entry_to_log(output)
                elif str(event_type) == "DEBUG":
                    self.add_debug_entry_to_log(output)
                elif str(event_type) == "WARNING":
                    self.add_warning_entry_to_log(output)
                else:
                    self.add_info_entry_to_log(output)
                return result

            return func_wrapper

        return decorator
