import Link from "next/link";

const books = [
  {
    id: "1",
    title: "The Little Web",
    author: "Alice",
    description: "A gentle introduction to web applications.",
    rating: 4,
  },
  {
    id: "2",
    title: "Flight Book",
    author: "Bob",
    description: "Notes about modern React rendering.",
    rating: 5,
  },
  {
    id: "3",
    title: "HTTP Field Guide",
    author: "Carol",
    description: "A small book about requests and responses.",
    rating: 3,
  },
];

export default function BooksPage() {
  return (
    <section>
      <p className="eyebrow">レビュー</p>
      <h1>書籍一覧</h1>
      <div className="book-grid">
        {books.map((book) => (
          <article key={book.id} className="book-card">
            <div>
              <p className="book-number">書籍 {book.id}</p>
              <h2>{book.title}</h2>
              <p className="muted">著者: {book.author}</p>
              <p>{book.description}</p>
            </div>
            <div className="card-footer">
              <span>評価: {book.rating} / 5</span>
              <Link href={`/books/${book.id}`}>詳細を見る</Link>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
