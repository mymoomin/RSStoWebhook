# Organisation of the database

This program was designed to use MongoDB Atlas, a decision made after a thorough technical consideration of its many benefits, such as not costing any money and also being free.
It should however work with any MongoDB instance with a URL.

The program does everything from a database with the name of the `DB_NAME` environment variable, using a collection called "comics" for most things, and one called "test-comics" for some testing.

The schema is as described in [db_types.py](/src/rss_to_webhook/db_types.py), reproduced here as TypeScript:

```ts
{
    _id: ObjectId,
    title: string,
    feed_url: string,  // Must be a valid URL

    color?: number  // Must be between 0x000000 and 0xFFFFF
    username?: string
    avatar_url?: string  // Must be a valid URL

    role_id: bigint
    thread_id?: bigint

    dailies: EntrySubset[]  // Must have valid URLs

    last_entries: EntrySubset[]
    feed_hash: bytes
    etag?: string
    last_modified?: string

    error_count?: bigint
    errors?: string[]
}
```
