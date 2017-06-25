#!/usr/bin/env python
"""
Form a subset of the Flickr Style data, download images to dirname, and write
Caffe ImagesDataLayer training file.
"""
import os
import urllib3
import hashlib
import argparse
import numpy as np
import pandas as pd
from skimage import io
import multiprocessing
from datetime import datetime
import threading
import Queue

# Flickr returns a special image if the request is unavailable.
MISSING_IMAGE_SHA1 = '6a92790b1c2a301c6e7ddef645dca1f53ea97ac2'

urlpath = './'
savepath = 'images/'


http = urllib3.PoolManager(10)
def download_image(args_tuple):
    "For use with multiprocessing map. Returns filename on fail."
    url, filename = args_tuple
    try:
        if not os.path.exists(filename):
            print url + ' -> ' + filename
            # Dont redirect.
            response = http.request('GET', url, redirect=False)
            with open(filename, 'wb') as f:
                f.write(response.data)
        with open(filename) as f:
            assert hashlib.sha1(f.read()).hexdigest() != MISSING_IMAGE_SHA1
        test_read_image = io.imread(filename)
        return True
    except KeyboardInterrupt:
        raise Exception()  # multiprocessing doesn't catch keyboard exceptions
    except:
        os.remove(filename)
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download a subset of Flickr Style to a directory')
    parser.add_argument(
        '-s', '--seed', type=int, default=0,
        help="random seed")
    parser.add_argument(
        '-i', '--images', type=int, default=-1,
        help="number of images to use (-1 for all [default])",
    )
    parser.add_argument(
        '-w', '--workers', type=int, default=-1,
        help="num workers used to download images. -x uses (all - x) cores [-1 default]."
    )
    parser.add_argument(
        '-l', '--labels', type=int, default=0,
        help="if set to a positive value, only sample images from the first number of labels."
    )

    args = parser.parse_args()
    np.random.seed(args.seed)

    # Read data, shuffle order, and subsample.
    csv_filename = os.path.join(urlpath, 'flickr_style.csv.gz')
    df = pd.read_csv(csv_filename, index_col=0, compression='gzip')
    df = df.iloc[np.random.permutation(df.shape[0])]
    if args.labels > 0:
        df = df.loc[df['label'] < args.labels]
    if args.images > 0 and args.images < df.shape[0]:
        df = df.iloc[:args.images]

    # Make directory for images and get local filenames.
    images_dirname = savepath
    if not os.path.exists(images_dirname):
        os.makedirs(images_dirname)
    df['image_filename'] = [
        os.path.join(images_dirname, _.split('/')[-1]) for _ in df['image_url']
    ]

    # Download images.
    num_workers = args.workers
    if num_workers <= 0:
        num_workers = multiprocessing.cpu_count() + num_workers
    print('Downloading {} images with {} workers...'.format(
        df.shape[0], num_workers))
    pool = multiprocessing.Pool(processes=8)
    map_args = zip(df['image_url'], df['image_filename'])
    results = pool.map(download_image,map_args)

    # Only keep rows with valid images, and write out training file lists.
    df = df[results]
    for split in ['train', 'test']:
        split_df = df[df['_split'] == split]
        filename = '{}.txt'.format(split)
        split_df[['image_filename', 'label']].to_csv(
            filename, sep=' ', header=None, index=None)
    print('Writing train/val for {} successfully downloaded images.'.format(
        df.shape[0]))
