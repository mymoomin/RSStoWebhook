function scrape() {
    url = document.querySelector("textarea[name='fields[feed_url]']").innerHTML;
    body = document.querySelector("textarea[name='fields[body]']").innerHTML;
    title = document.querySelectorAll("input[type=text]")[8].value;
    name = title.match(/^.+?(?= web)/);
    role_id = BigInt(body.match(/amp;(.+?)&/)[1]);
    color = parseInt(body.match(/: (\d+)/)[1]);
    let author = {};
    author.name = body.match(/"name": "(.+?)"/)[1];
    author.url = body.match(/"(http.+)"/)[1];
    copy({
        name,
        url,
        role_id,
        color,
        author,
    });
    return name;
}
scrape();
