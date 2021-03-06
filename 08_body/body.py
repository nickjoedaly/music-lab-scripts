# -*- coding: utf-8 -*-
##
# TRACK 8
# BODY LANGUAGE
# Brian Foo (brianfoo.com)
# This file builds the sequence file for use with ChucK from the data supplied
##

# Library dependancies
import csv
import json
import math
import os
from pprint import pprint
import sys
import time

# Config
BPM = 100 # Beats per minute, e.g. 60, 75, 100, 120, 150
DIVISIONS_PER_BEAT = 8 # e.g. 4 = quarter notes, 8 = eighth notes, etc
VARIANCE_MS = 20 # +/- milliseconds an instrument note should be off by to give it a little more "natural" feel
GAIN = 0.4 # base gain
TEMPO = 1.0 # base tempo
MS_PER_ARTIST = 12000
REGION_COUNT = 3 # number of artist's top-mentioned body regions to look at
PROBABILITY_MULITPLIER = 0.8 # make it more or less likely to say a body part

# Files
INSTRUMENTS_INPUT_FILE = 'data/instruments.csv'
ARTISTS_INPUT_FILE = 'data/artists.csv'
ANALYSIS_INPUT_FILE = 'data/analysis.json'
SUMMARY_OUTPUT_FILE = 'data/report_summary.csv'
SUMMARY_SEQUENCE_OUTPUT_FILE = 'data/report_sequence.csv'
INSTRUMENTS_OUTPUT_FILE = 'data/ck_instruments.csv'
SEQUENCE_OUTPUT_FILE = 'data/ck_sequence.csv'
VIZ_OUTPUT_FILE = 'visualization/data/visualization.json'
INSTRUMENTS_DIR = 'instruments/'

# Output options
WRITE_SEQUENCE = True
WRITE_REPORT = True
WRITE_VIZ = True

# Calculations
BEAT_MS = round(60.0 / BPM * 1000)
ROUND_TO_NEAREST = round(BEAT_MS / DIVISIONS_PER_BEAT)
BEATS_PER_ARTIST = round(MS_PER_ARTIST / BEAT_MS)

# Init
artist_sequence = []
artists = []
instruments = []
sequence = []
hindex = 0
hindex_instrument = 0

# For creating pseudo-random numbers
def halton(index, base):
    result = 0.0
    f = 1.0 / base
    i = 1.0 * index
    while(i > 0):
        result += f * (i % base)
        i = math.floor(i / base)
        f = f / base
    return result

# floor {n} to nearest {nearest}
def floorToNearest(n, nearest):
    return 1.0 * math.floor(1.0*n/nearest) * nearest

# round {n} to nearest {nearest}
def roundToNearest(n, nearest):
    return 1.0 * round(1.0*n/nearest) * nearest

# Read instruments from file
with open(INSTRUMENTS_INPUT_FILE, 'rb') as f:
    r = csv.reader(f, delimiter=',')
    next(r, None) # remove header
    for file, artist, region, gender, from_gain, to_gain, from_tempo, to_tempo, tempo_offset, interval_phase, interval, interval_offset, active in r:
        if int(active):
            index = len(instruments)
            # build instrument object
            _beat_ms = int(round(BEAT_MS/TEMPO))
            instrument = {
                'index': index,
                'file': INSTRUMENTS_DIR + file,
                'artist': artist.decode('utf-8'),
                'region': region,
                'gender': gender,
                'from_gain': float(from_gain) * GAIN,
                'to_gain': float(to_gain) * GAIN,
                'from_tempo': float(from_tempo) * TEMPO,
                'to_tempo': float(to_tempo) * TEMPO,
                'tempo_offset': float(tempo_offset),
                'interval_ms': int(int(interval_phase)*_beat_ms),
                'interval': int(interval),
                'interval_offset': int(interval_offset),
                'from_beat_ms': int(round(BEAT_MS/(float(from_tempo)*TEMPO))),
                'to_beat_ms': int(round(BEAT_MS/(float(to_tempo)*TEMPO))),
                'beat_ms': _beat_ms
            }
            # add instrument to instruments
            instruments.append(instrument)

# Read artists from file
with open(ANALYSIS_INPUT_FILE) as data_file:
    artists = json.load(data_file)

with open(ARTISTS_INPUT_FILE) as csvfile:
    artist_sequence = csv.DictReader(csvfile)

    # Re-order artists based on sequence
    artists_temp = artists[:]
    artists = []
    for i, a in enumerate(artist_sequence):
        artist = next(iter([_a for _a in artists_temp if a['name']==_a['artist'].encode('utf-8')]), None)
        artist['index'] = i
        artists.append(artist)

# Calculate total time
total_ms = len(artists) * MS_PER_ARTIST
total_seconds = int(1.0*total_ms/1000)
print('Main sequence time: '+time.strftime('%M:%S', time.gmtime(total_seconds)) + ' (' + str(total_seconds) + 's)')
print('Ms per beat: ' + str(BEAT_MS))
print('Beats per artist: ' + str(BEATS_PER_ARTIST))

# Multiplier based on sine curve
def getMultiplier(percent_complete, rad=1.0):
    radians = percent_complete * (math.pi * rad)
    multiplier = math.sin(radians)
    if multiplier < 0:
        multiplier = 0.0
    elif multiplier > 1:
        multplier = 1.0
    return multiplier

# Retrieve gain based on current beat
def getGain(instrument, percent_complete):
    multiplier = getMultiplier(percent_complete)
    from_gain = instrument['from_gain']
    to_gain = instrument['to_gain']
    min_gain = min(from_gain, to_gain)
    gain = multiplier * (to_gain - from_gain) + from_gain
    gain = max(min_gain, round(gain, 2))
    return gain

# Get beat duration in ms based on current point in time
def getBeatMs(instrument, percent_complete, round_to):
    multiplier = getMultiplier(percent_complete)
    from_beat_ms = instrument['from_beat_ms']
    to_beat_ms = instrument['to_beat_ms']
    ms = multiplier * (to_beat_ms - from_beat_ms) + from_beat_ms
    ms = int(roundToNearest(ms, round_to))
    return ms

# Return if the instrument should be played in the given interval
def isValidInterval(instrument, elapsed_ms):
    interval_ms = instrument['interval_ms']
    interval = instrument['interval']
    interval_offset = instrument['interval_offset']
    return int(math.floor(1.0*elapsed_ms/interval_ms)) % interval == interval_offset

# Add beats to sequence
def addBeatsToSequence(region, instrument, duration, ms, round_to):
    global sequence
    global hindex
    global hindex_instrument

    beat_ms = int(roundToNearest(instrument['beat_ms'], round_to))
    offset_ms = int(instrument['tempo_offset'] * instrument['from_beat_ms'])
    ms += offset_ms
    previous_ms = int(ms)
    from_beat_ms = instrument['from_beat_ms']
    to_beat_ms = instrument['to_beat_ms']
    min_ms = min(from_beat_ms, to_beat_ms)
    remaining_duration = int(duration)
    elapsed_duration = offset_ms
    while remaining_duration >= min_ms:
        elapsed_ms = int(ms)
        elapsed_beat = int((elapsed_ms-previous_ms) / beat_ms)
        percent_complete = 1.0 * elapsed_duration / duration
        this_beat_ms = getBeatMs(instrument, percent_complete, round_to)
        # add to sequence if in valid interval
        if isValidInterval(instrument, elapsed_ms):
            if instrument['region'] == 'all':
                h_i = -1
            else:
                h_i = halton(hindex_instrument, 5)
                hindex_instrument += 1
            if h_i < region['value_n'] * PROBABILITY_MULITPLIER:
                h = halton(hindex, 3)
                variance = int(h * VARIANCE_MS * 2 - VARIANCE_MS)
                sequence.append({
                    'instrument_index': instrument['index'],
                    'instrument': instrument,
                    'position': 0,
                    'rate': 1,
                    'gain': getGain(instrument, percent_complete),
                    'elapsed_ms': max([elapsed_ms + variance, 0]),
                    'duration': min([this_beat_ms, MS_PER_ARTIST])
                })
                hindex += 1
        remaining_duration -= this_beat_ms
        elapsed_duration += this_beat_ms
        ms += this_beat_ms

# Build sequence
for i in instruments:
    ms = 0
    hindex_instrument = 0

    # Go through each artist
    for a in artists:

        # Go through top x regions
        regions = a['regions_agnostic'][:REGION_COUNT]
        for r in regions:

            if a['artist']==i['artist'] and (r['name']==i['region'] or i['region']=='all'):
                addBeatsToSequence(r.copy(), i.copy(), MS_PER_ARTIST, ms, ROUND_TO_NEAREST)

        ms += MS_PER_ARTIST

# Sort sequence
sequence = sorted(sequence, key=lambda k: k['elapsed_ms'])

# Add milliseconds to sequence
elapsed = 0
for i, step in enumerate(sequence):
    sequence[i]['milliseconds'] = step['elapsed_ms'] - elapsed
    elapsed = step['elapsed_ms']

# Write instruments to file
if WRITE_SEQUENCE and len(instruments) > 0:
    with open(INSTRUMENTS_OUTPUT_FILE, 'wb') as f:
        w = csv.writer(f)
        for index, instrument in enumerate(instruments):
            w.writerow([index])
            w.writerow([instrument['file']])
        f.seek(-2, os.SEEK_END) # remove newline
        f.truncate()
        print('Successfully wrote instruments to file: '+INSTRUMENTS_OUTPUT_FILE)

# Write sequence to file
if WRITE_SEQUENCE and len(sequence) > 0:
    with open(SEQUENCE_OUTPUT_FILE, 'wb') as f:
        w = csv.writer(f)
        for step in sequence:
            w.writerow([step['instrument_index']])
            w.writerow([step['position']])
            w.writerow([step['gain']])
            w.writerow([step['rate']])
            w.writerow([step['milliseconds']])
        f.seek(-2, os.SEEK_END) # remove newline
        f.truncate()
        print('Successfully wrote sequence to file: '+SEQUENCE_OUTPUT_FILE)

# Write summary files
if WRITE_REPORT and len(sequence) > 0:

    with open(SUMMARY_OUTPUT_FILE, 'wb') as f:
        w = csv.writer(f)
        w.writerow(['Artist', 'Region', 'Percent'])
        valid_regions = ['eye','face','hand','heart','mouth','foot','arm','butt','groin']
        for a in artists:
            for r in valid_regions:
                region = next(iter([_r for _r in a['regions_agnostic'] if _r['name']==r]), None)
                if region is None:
                    w.writerow([a['artist'].encode('utf-8'), r, 0])
                else:
                    w.writerow([a['artist'].encode('utf-8'), r, 1.0 * region['value'] / a['value_count']])
            others = sum([r['value'] for r in a['regions_agnostic'] if r['name'] not in valid_regions])
            w.writerow([a['artist'].encode('utf-8'), 'other', 1.0 * others / a['value_count']])
        print('Successfully wrote report to file: '+SUMMARY_OUTPUT_FILE)

    with open(SUMMARY_SEQUENCE_OUTPUT_FILE, 'wb') as f:
        w = csv.writer(f)
        w.writerow(['Time', 'Instrument', 'Gain'])
        for step in sequence:
            instrument = instruments[step['instrument_index']]
            elapsed = step['elapsed_ms']
            elapsed_f = time.strftime('%M:%S', time.gmtime(int(elapsed/1000)))
            ms = int(elapsed % 1000)
            elapsed_f += '.' + str(ms)
            w.writerow([elapsed_f, instrument['file'], step['gain']])
        f.seek(-2, os.SEEK_END) # remove newline
        f.truncate()
        print('Successfully wrote sequence report to file: '+SUMMARY_SEQUENCE_OUTPUT_FILE)

def getDuration(wav_file):
    duration = 0
    with open(wav_file, "r") as f:
        # read the ByteRate field from file (see the Microsoft RIFF WAVE file format)
        # https://ccrma.stanford.edu/courses/422/projects/WaveFormat/
        # ByteRate is located at the first 28th byte
        f.seek(28)
        a = f.read(4)

        # convert string a into integer/longint value
        # a is little endian, so proper conversion is required
        byteRate = 0
        for i in range(4):
            byteRate = byteRate + ord(a[i]) * pow(256,i)

        # get the file size in bytes
        fileSize = os.path.getsize(wav_file)

        # the duration of the data, in milliseconds, is given by
        duration = (fileSize - 44) * 1000 / byteRate

    return duration

if WRITE_VIZ and len(sequence) > 0:

    # measure the durations of all audio files
    files = set([i['file'] for i in instruments if i['region'] != 'all'])
    file_durations = {}
    for f in files:
        d = getDuration(f)
        file_durations[f] = d

    # add ms to artists
    ms = 0
    for i, a in enumerate(artists):
        artists[i]['start_ms'] = ms
        artists[i]['end_ms'] = ms + MS_PER_ARTIST
        artists[i]['instruments'] = []
        ms += MS_PER_ARTIST

    # build instrument sequence
    for step in sequence:

        i = step['instrument']
        if i['file'] not in file_durations:
            continue
        duration = file_durations[i['file']]

        # Retrieve artist
        artist = next(iter([a for a in artists if i['artist']==a['artist']]), None)

        # Determine instrument's regions
        instrument_regions = []
        if i['gender'] == 'both':
            instrument_regions = ['female_' + i['region'], 'male_' + i['region']]
        else:
            instrument_regions = [i['gender'] + '_' + i['region']]

        # Add instruments to artists
        for r in instrument_regions:
            artists[artist['index']]['instruments'].append({
                'region': r,
                'start_ms': step['elapsed_ms'],
                'end_ms': step['elapsed_ms'] + duration
            })

    with open(VIZ_OUTPUT_FILE, 'w') as outfile:
        json.dump(artists, outfile)
        print('Successfully wrote viz data to file: '+VIZ_OUTPUT_FILE)
