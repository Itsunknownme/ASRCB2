import time as tm
from database import db 
from .test import parse_buttons
# Assuming you have database imports in utils.py (or need to add them)
import re
from database import db
# ... other existing imports ...

# ================== CAPTION CLEANING FUNCTION ==================#
async def clean_caption(user_id: int, caption: str) -> str:
    """Removes configured words from the given caption."""
    if not caption:
        return ""
    
    # 1. Fetch the list of words to remove from the database
    words_to_remove = await db.get_remove_words(user_id)
    
    if not words_to_remove:
        return caption
        
    # Create a set of words for fast lookup and convert to lowercase
    remove_set = {word.lower() for word in words_to_remove}
    
    # 2. Split the caption into words
    parts = re.split(r'(\s+)', caption)
    
    cleaned_parts = []
    
    for part in parts:
        if part.strip():
            # Simple word extraction (remove non-word characters from start/end)
            simple_word = re.sub(r'^\W+|\W+$', '', part).lower()
            
            if simple_word not in remove_set:
                cleaned_parts.append(part)
        else:
            # Keep the whitespace separator
            cleaned_parts.append(part)
            
    # 3. Rejoin the parts to form the new caption
    return "".join(cleaned_parts).strip()
    
STATUS = {}

class STS:
    def __init__(self, id):
        self.id = id
        self.data = STATUS
    
    def verify(self):
        return self.data.get(self.id)
    
    def store(self, From, to,  skip, limit):
        self.data[self.id] = {"FROM": From, 'TO': to, 'total_files': 0, 'skip': skip, 'limit': limit,
                      'fetched': skip, 'filtered': 0, 'deleted': 0, 'duplicate': 0, 'total': limit, 'start': 0}
        self.get(full=True)
        return STS(self.id)
        
    def get(self, value=None, full=False):
        values = self.data.get(self.id)
        if not full:
           return values.get(value)
        for k, v in values.items():
            setattr(self, k, v)
        return self

    def add(self, key=None, value=1, time=False):
        if time:
          return self.data[self.id].update({'start': tm.time()})
        self.data[self.id].update({key: self.get(key) + value}) 
    
    def divide(self, no, by):
       by = 1 if int(by) == 0 else by 
       return int(no) / by 
    
    async def get_data(self, user_id):
        bot = await db.get_bot(user_id)
        k, filters = self, await db.get_filters(user_id)
        size, configs = None, await db.get_configs(user_id)
        if configs['duplicate']:
           duplicate = [configs['db_uri'], self.TO]
        else:
           duplicate = False
        button = parse_buttons(configs['button'] if configs['button'] else '')
        if configs['file_size'] != 0:
            size = [configs['file_size'], configs['size_limit']]
        return bot, configs['caption'], configs['forward_tag'], {'chat_id': k.FROM, 'limit': k.limit, 'offset': k.skip, 'filters': filters,
                'keywords': configs['keywords'], 'media_size': size, 'extensions': configs['extension'], 'skip_duplicate': duplicate}, configs['protect'], button
        
