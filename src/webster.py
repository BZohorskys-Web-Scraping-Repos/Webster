import aiohttp
import asyncio
import curses
import itertools
import logging
import pprint
import webbrowser

from lxml import html

BASE_WORD_OF_THE_DAY_URL = 'https://www.merriam-webster.com/word-of-the-day/'
BASE_URL = 'https://www.merriam-webster.com/'

logging.basicConfig(
    level=logging.WARN,
    format='%(asctime)-15s [%(levelname)s] %(funcName)s: %(message)s',
)

#Logging Example
#logging.info(locals())

def get_definitions(webpage, url):
    word = webpage.xpath('//h1[@class="hword"]/text()')[0].title()
    syllables = ''.join(webpage.xpath('//div[@class="row entry-attr"]')[0].xpath('.//span[@class="word-syllables"]/text()'))
    pronunciation = webpage.xpath('//span[@class="pr"]/text()')[0].strip()
    definitions = []
    entries = webpage.xpath('//div[contains(@id,"dictionary-entry")]')
    for entryIdx in range(len(entries)):
        if entryIdx >= len(webpage.xpath('//div[contains(@class,"entry-header")]/div/span/a/text()')):
            continue
        part_of_speech = entries[entryIdx].xpath('./preceding-sibling::div[contains(@class,"entry-header")]/div/span/a/text()')[entryIdx].title()
        definitionGroups = entries[entryIdx].xpath('.//div[@class="vg"]')
        for group in definitionGroups:
            if len(group.xpath('./p[contains(@class,"vd")]')):
                part_of_speech = group.xpath('./p[contains(@class,"vd")]/a/text()')[0].title()
            definitionTables = group.xpath('.//span[contains(@class,"dt ")]')
            for table in definitionTables:
                rows = table.xpath('./span[@class="dtText"]')
                for row in rows:
                    value = format_definition_value(''.join(row.xpath('./descendant-or-self::*/text()')))
                    if len(row.xpath('./following-sibling::span[contains(@class,"ex-sent")]')):
                        example = format_definition_example(''.join(row.xpath('./following-sibling::span[contains(@class,"ex-sent")]')[0].xpath('./descendant-or-self::*/text()')))
                    else:
                        example = ''
                    definitions.append(
                        {
                            'example':example,
                            'part_of_speech':part_of_speech,
                            'pronunciation':pronunciation,
                            'syllables':syllables,
                            'url': url,
                            'value':value,
                            'word':word,
                        }
                    )
    return definitions

def format_definition_value(value):
    value = value.strip()
    if value[0:2] == ': ':
        value = value[2:]
    value = value[0].capitalize() + value[1:]
    return value

def format_definition_example(example):
    example = example[0].capitalize() + example[1:]
    return example

def get_synonyms(webpage, url):
    word = webpage.xpath('//h1[@class="hword"]/text()')[0].title()
    synonyms = []
    entries = webpage.xpath('//div[contains(@id,"thesaurus-entry")]')
    for entryIdx in range(len(entries)):
        if entryIdx >= len(webpage.xpath('//div[contains(@class,"entry-header")]/div/span/a/text()')):
            continue
        part_of_speech = entries[entryIdx].xpath('./preceding-sibling::div[contains(@class,"entry-header")]/div/span/a/text()')[entryIdx].title()
        definitionGroups = entries[entryIdx].xpath('.//div[@class="vg"]')
        for group in definitionGroups:
            if len(group.xpath('./p[contains(@class,"vd")]')):
                part_of_speech = group.xpath('./p[contains(@class,"vd")]/a/text()')[0].title()
            definitionTables = group.xpath('./div[contains(@class,"sb ")]')
            for table in definitionTables:
                rows = table.xpath('.//span[contains(@class,"dt ")]')
                for row in rows:
                    if len(row.xpath('./ul/li/span[@class="t"]')):
                        example = format_definition_example(''.join(row.xpath('./ul/li/span[@class="t"]')[0].xpath('./descendant-or-self::*/text()')))
                    else:
                        example = ''
                    value = ', '.join(row.xpath('./following-sibling::span[contains(@class,"syn-list")]//div[contains(@class,"synonyms_list")]/ul/li/a/text()'))
                    for duplicate_data in row.xpath('./ul'):
                        duplicate_data.getparent().remove(duplicate_data)
                    definition = format_definition_value(''.join(row.xpath('./descendant-or-self::*/text()')).strip())
                    synonyms.append({
                        'definition': definition,
                        'example': example,
                        'part_of_speech': part_of_speech,
                        'url': url,
                        'value': value,
                        'word': word,
                    })
    return synonyms

async def get_word_of_the_day():
    data = {}
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_WORD_OF_THE_DAY_URL) as response:
            code = response.status
            if code != 200:
                data['error'] = 'Error: A {0} was recieved while tring to complete the request.'.format(code)
            else:
                webpage = html.fromstring(await response.text())
                data['word'] = webpage.xpath('//div[@class="word-and-pronunciation"]/h1/text()')[0]
    return data


async def get_query_data(word):
    data = {}
    dictionary_search_url = BASE_URL + 'dictionary/' + word
    thesaurus_search_url = BASE_URL + 'thesaurus/' + word
    async with aiohttp.ClientSession() as session:
        async with session.get(dictionary_search_url) as response:
            code = response.status
            if code != 200:
                data['error'] = 'Error: A {0} was recieved while tring to complete the request.'.format(code)
            else:
                data['definitions'] = get_definitions(html.fromstring(await response.text()), dictionary_search_url)

        async with session.get(thesaurus_search_url) as response:
            code = response.status
            if code != 200 or 'error' in data:
                data['error'] = 'Error: A {0} was recieved while tring to complete the request.'.format(code)
            else:
                data['synonyms'] = get_synonyms(html.fromstring(await response.text()), thesaurus_search_url)
    return data

async def idleAnimation(task):
    for frame in itertools.cycle(r'-\|/'):
        if task.done():
            print('\r', '', sep='', end='', flush=True)
            break;
        print('\r', '', sep='', end='', flush=True)
        await asyncio.sleep(0.2)

def interactive_console(screen,data):
    key = 'definitions'
    index_memory = {
        'definitions': 0,
        'synonyms': 0,
    }
    idx = 0
    while idx < len(data[key]):
        screen.clear()
        if key == 'definitions':
            print_definition(screen, data[key][idx], idx, len(data[key]))
        elif key == 'synonyms':
            print_synonyms(screen, data[key][idx], idx, len(data[key]))
        valid_response = False
        while not valid_response:
            user_response = screen.getkey()
            if user_response == 'j':
                valid_response = True
                idx += 1
            elif user_response == 'k':
                if idx == 0:
                    pass
                else:
                    valid_response = True
                    idx -= 1
            elif user_response == 'o':
                webbrowser.open(data[key][idx]['url'])
            elif user_response == 'h':
                index_memory[key] = idx
                key = 'definitions'
                idx = index_memory[key]
                valid_response = True
            elif user_response == 'l':
                index_memory[key] = idx
                key = 'synonyms'
                idx = index_memory[key]
                valid_response = True
            elif user_response == 'q':
                idx = len(data[key])
                valid_response = True

def print_definition(screen, definition, idx, definitions_len):
        screen.addstr(definition['word'] + ' (' + str(idx + 1) + '/' + str(definitions_len) + ') Dictionary\n')
        if definition['syllables'] != '':
            screen.addstr('Syllables: ' + definition['syllables'] + '\n')
        screen.addstr('Pronunciation: ' + definition['pronunciation'] + '\n')
        screen.addstr('Part of Speech: ' + definition['part_of_speech'] + '\n')
        screen.addstr('Definition: ' + definition['value'] + '\n')
        if definition['example'] != '':
            screen.addstr('Example: ' + definition['example'] + '\n')
        screen.addstr('\nNext, Previous, Open, Thesaurus, Quit. (j,k,o,l,q)')

def print_synonyms(screen, synonym, idx, definitions_len):
        screen.addstr(synonym['word'] + ' (' + str(idx + 1) + '/' + str(definitions_len) + ') Thesaurus\n')
        screen.addstr('Part of Speech: ' + synonym['part_of_speech'] + '\n')
        screen.addstr('Definition: ' + synonym['definition'] + '\n')
        if synonym['example'] != '':
            screen.addstr('Example: ' + synonym['example'] + '\n')
        screen.addstr('Synonyms: ' + synonym['value'] + '\n')
        screen.addstr('\nNext, Previous, Open, Dictionary, Quit. (j,k,o,h,q)')

async def search(word):
    searchTask = asyncio.create_task(get_query_data(word))
    await idleAnimation(searchTask)
    if 'error' in searchTask.result():
        print(searchTask.result()['error'])
    else:
        curses.wrapper(interactive_console, searchTask.result())

async def word_of_the_day_search():
    word_of_the_day_task = asyncio.create_task(get_word_of_the_day())
    await idleAnimation(word_of_the_day_task)
    if 'error' in word_of_the_day_task.result():
        print(word_of_the_day_task.result()['error'])
        return
    searchTask = asyncio.create_task(get_query_data(word_of_the_day_task.result()['word']))
    await idleAnimation(searchTask)
    if 'error' in searchTask.result():
        print(searchTask.result()['error'])
    else:
        curses.wrapper(interactive_console, searchTask.result())