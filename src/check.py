import re

class CHECK:
    def check_youtube(url):
        youtube_regex = (
            r'^(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=[\w-]+(&t=\d+s)?|playlist\?list=[\w-]+|.*?/[\w-]+)$'
        )
        return bool(re.match(youtube_regex, url))