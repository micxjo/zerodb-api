import transaction
import zerodb
from zerodb.models import Model, fields

TEST_PASSPHRASE = "v3ry 53cr3t pa$$w0rd"


class Page(Model):
    title = fields.Field()
    text = fields.Text()
    num = fields.Field()


def create_objects_and_close(sock, count=200, dbclass=zerodb.DB):
    db = dbclass(sock, username="root", password=TEST_PASSPHRASE, debug=True)
    with transaction.manager:
        count = 0
        for i in list(range(count / 2)) + list(range(count / 2 + 10, count)):
            db.add(Page(title="hello %s" % i,
                        text="lorem ipsum dolor sit amet" * 50,
                        num=count))
            count += 1
        for i in range(count / 2, count / 2 + 10):
            db.add(Page(title="hello %s" % i,
                        text="this is something we're looking for" * 50,
                        num=count))
            count += 1
        db.add(Page(title="one two",
                    text='''"The quick brown fox jumps over a lazy dog" is an
                             English-language pangram - a phrase that contains
                             all of the letters of the alphabet.''',
                    num=count))
    db.disconnect()
