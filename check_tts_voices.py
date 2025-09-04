#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import edge_tts

async def main():
    voices = await edge_tts.list_voices()
    
    print('\nEdge-TTS支持的马来语语音：')
    for voice in voices:
        if 'ms-MY' in voice['ShortName']:
            print(f'{voice["ShortName"]} - {voice["DisplayName"]}')
    
    print('\nEdge-TTS支持的泰语语音：')
    for voice in voices:
        if 'th-TH' in voice['ShortName']:
            print(f'{voice["ShortName"]} - {voice["DisplayName"]}')

if __name__ == '__main__':
    asyncio.run(main())