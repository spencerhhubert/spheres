#!/usr/bin/env python3

import json
import requests
from bs4 import BeautifulSoup
from typing import TypedDict, Optional, Dict, List
import time
import os
import re


class ExternalIds(TypedDict, total=False):
    BrickLink: List[str]
    BrickOwl: List[str]
    Brickset: List[str]
    LDraw: List[str]
    LEGO: List[str]
    Peeron: List[str]


class RebrickablePartResult(TypedDict):
    part_num: str
    name: str
    part_cat_id: int
    part_url: str
    part_img_url: str
    external_ids: ExternalIds


class RebrickableResponse(TypedDict):
    count: int
    next: Optional[str]
    previous: Optional[str]
    results: List[RebrickablePartResult]


class BrickPiece(TypedDict):
    name: str
    id: str
    overall_rank: int
    num_pieces: int
    num_sets: int
    num_colors: int
    begin_year: int
    end_year: int
    total_years: int
    weight: Optional[float]
    pack_dim_x: Optional[float]
    pack_dim_y: Optional[float]
    pack_dim_z: Optional[float]
    rebrickable_part_num: Optional[str]
    external_ids: Optional[ExternalIds]


BRICKARCHITECT_BASE_URL = "https://brickarchitect.com/parts/most-common-allyears"
BRICKLINK_BASE_URL = "https://www.bricklink.com/v2/catalog/catalogitem.page"
REBRICKABLE_BASE_URL = "https://rebrickable.com/api/v3/lego/parts/"
OUTPUT_FILE = "parts.json"
MAX_PAGES = 100
SLEEP_DURATION = 0.1
BRICKLINK_SLEEP_DURATION = 2
REBRICKABLE_API_KEY = os.environ.get('REBRICKABLE_API_KEY', '')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def getRebrickableData(lego_id: str) -> tuple[Optional[str], Optional[str], Optional[ExternalIds]]:
    url = f"{REBRICKABLE_BASE_URL}?lego_id={lego_id}"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'key {REBRICKABLE_API_KEY}'
    }

    try:
        print(f"    Querying Rebrickable for lego_id {lego_id}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data: RebrickableResponse = response.json()

        if data['count'] > 0 and len(data['results']) > 0:
            result = data['results'][0]
            part_num = result.get('part_num')
            external_ids = result.get('external_ids', {})

            bricklink_id = None
            if 'BrickLink' in external_ids and len(external_ids['BrickLink']) > 0:
                bricklink_id = external_ids['BrickLink'][0]
                print(f"    Found BrickLink ID: {bricklink_id}")
            else:
                print(f"    Warning: No BrickLink ID found in Rebrickable data")

            return bricklink_id, part_num, external_ids
        else:
            print(f"    Warning: No results found in Rebrickable for lego_id {lego_id}")
            return None, None, None

    except Exception as e:
        print(f"    Error querying Rebrickable for {lego_id}: {e}")
        return None, None, None


def scrapeBricklinkData(part_id: str) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    url = f"{BRICKLINK_BASE_URL}?P={part_id}"

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        weight = None
        pack_dim_x = None
        pack_dim_y = None
        pack_dim_z = None

        weight_elem = soup.select_one('#item-weight-info')
        if weight_elem:
            weight_text = weight_elem.get_text(strip=True)
            print(f"    Weight text found: '{weight_text}'")
            weight_match = re.search(r'([\d.]+)g?', weight_text)
            if weight_match:
                weight = float(weight_match.group(1))
                print(f"    Weight parsed: {weight}g")
            else:
                print(f"    Warning: Could not parse weight from '{weight_text}'")
        else:
            print(f"    Warning: #item-weight-info element not found")

        dim_spans = soup.select('span[id="dimSec"]')
        print(f"    Found {len(dim_spans)} span[id='dimSec'] elements")
        for i, span in enumerate(dim_spans):
            dim_text = span.get_text(strip=True)
            print(f"    Dim span {i}: '{dim_text}'")
            if 'cm' in dim_text:
                dim_match = re.findall(r'([\d.]+)', dim_text)
                if len(dim_match) >= 3:
                    pack_dim_x = float(dim_match[0])
                    pack_dim_y = float(dim_match[1])
                    pack_dim_z = float(dim_match[2])
                    print(f"    Dimensions parsed: {pack_dim_x} x {pack_dim_y} x {pack_dim_z} cm")
                    break
                else:
                    print(f"    Warning: Found 'cm' but only {len(dim_match)} numbers in '{dim_text}'")

        if pack_dim_x is None:
            print(f"    Warning: No valid pack dimensions found")

        time.sleep(BRICKLINK_SLEEP_DURATION)
        return weight, pack_dim_x, pack_dim_y, pack_dim_z

    except Exception as e:
        print(f"  Error scraping bricklink for part {part_id}: {e}")
        return None, None, None, None


def scrapePage(page_num: int, all_pieces: list[BrickPiece], existing_parts_dict: Dict[str, BrickPiece]) -> int:
    url = f"{BRICKARCHITECT_BASE_URL}?page={page_num}"
    print(f"Scraping page {page_num}...")

    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    pieces_count = 0

    rows = soup.select('.parts_results.tablestyle.mostcommon .tbody .tr')

    for row in rows:
        part_name_elem = row.select_one('.partname')
        part_num_elem = row.select_one('.partnum')

        if not part_name_elem or not part_num_elem:
            continue

        rank_elem = row.select_one('.weighted_rank.selected')
        num_pieces_elem = row.select_one('.num_pieces .largetext')
        num_sets_elem = row.select_one('.num_sets .largetext')
        num_colors_elem = row.select_one('.num_colors .largetext')
        years_elem = row.select_one('.years_produced .largetext')
        total_years_elem = row.select_one('.years_produced .smalltext')

        years_text = years_elem.get_text(strip=True) if years_elem else ""
        begin_year = 0
        end_year = 0

        if years_text and '-' in years_text:
            year_parts = years_text.split('-')
            begin_year = int(year_parts[0])
            end_year = int(year_parts[1])

        total_years_text = total_years_elem.get_text(strip=True) if total_years_elem else "0"
        total_years = int(total_years_text.split()[0]) if total_years_text else 0

        part_id = part_num_elem.get_text(strip=True)

        if part_id in existing_parts_dict:
            existing_piece = existing_parts_dict[part_id]
            print(f"  Part {part_id} already scraped, skipping Rebrickable/BrickLink...")

            piece: BrickPiece = {
                'name': part_name_elem.get_text(strip=True),
                'id': part_id,
                'overall_rank': int(rank_elem.get_text(strip=True)) if rank_elem else 0,
                'num_pieces': int(num_pieces_elem.get_text(strip=True).replace(',', '')) if num_pieces_elem else 0,
                'num_sets': int(num_sets_elem.get_text(strip=True).replace(',', '')) if num_sets_elem else 0,
                'num_colors': int(num_colors_elem.get_text(strip=True)) if num_colors_elem else 0,
                'begin_year': begin_year,
                'end_year': end_year,
                'total_years': total_years,
                'weight': existing_piece.get('weight'),
                'pack_dim_x': existing_piece.get('pack_dim_x'),
                'pack_dim_y': existing_piece.get('pack_dim_y'),
                'pack_dim_z': existing_piece.get('pack_dim_z'),
                'rebrickable_part_num': existing_piece.get('rebrickable_part_num'),
                'external_ids': existing_piece.get('external_ids')
            }
        else:
            print(f"  Processing part {part_id}...")
            bricklink_id, rebrickable_part_num, external_ids = getRebrickableData(part_id)

            weight = None
            pack_dim_x = None
            pack_dim_y = None
            pack_dim_z = None

            if bricklink_id:
                print(f"  Scraping bricklink data for BrickLink ID {bricklink_id}...")
                weight, pack_dim_x, pack_dim_y, pack_dim_z = scrapeBricklinkData(bricklink_id)
            else:
                print(f"  Skipping BrickLink scrape (no BrickLink ID found)")

            piece: BrickPiece = {
                'name': part_name_elem.get_text(strip=True),
                'id': part_id,
                'overall_rank': int(rank_elem.get_text(strip=True)) if rank_elem else 0,
                'num_pieces': int(num_pieces_elem.get_text(strip=True).replace(',', '')) if num_pieces_elem else 0,
                'num_sets': int(num_sets_elem.get_text(strip=True).replace(',', '')) if num_sets_elem else 0,
                'num_colors': int(num_colors_elem.get_text(strip=True)) if num_colors_elem else 0,
                'begin_year': begin_year,
                'end_year': end_year,
                'total_years': total_years,
                'weight': weight,
                'pack_dim_x': pack_dim_x,
                'pack_dim_y': pack_dim_y,
                'pack_dim_z': pack_dim_z,
                'rebrickable_part_num': rebrickable_part_num,
                'external_ids': external_ids
            }

        all_pieces.append(piece)
        saveData(all_pieces)
        pieces_count += 1

    return pieces_count


def loadExistingData() -> list[BrickPiece]:
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('pieces', [])
    return []


def saveData(pieces_list: list[BrickPiece]):
    output = {'pieces': pieces_list}
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def main():
    existing_pieces = loadExistingData()
    existing_parts_dict = {piece['id']: piece for piece in existing_pieces}
    print(f"Loaded {len(existing_parts_dict)} existing parts from cache")

    all_pieces: list[BrickPiece] = []
    page = 1

    while page <= MAX_PAGES:
        try:
            pieces_count = scrapePage(page, all_pieces, existing_parts_dict)

            if pieces_count == 0:
                print(f"No more data found at page {page}. Stopping.")
                break

            print(f"Found {pieces_count} pieces on page {page} (total: {len(all_pieces)})")

            page += 1
            time.sleep(SLEEP_DURATION)

        except Exception as e:
            print(f"Error on page {page}: {e}")
            break

    print(f"\nScraping complete! Total {len(all_pieces)} pieces saved to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
