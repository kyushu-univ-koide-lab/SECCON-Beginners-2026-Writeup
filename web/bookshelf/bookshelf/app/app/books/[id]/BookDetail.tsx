"use client";

export type Book = {
  id: string;
  title: string;
  author: string;
  description: string;
  rating: number;
  internalNote?: string;
};

type BookDetailProps = {
  book: Book;
};

export default function BookDetail({ book }: BookDetailProps) {
  return (
    <article className="detail-panel">
      <p className="book-number">書籍 {book.id}</p>
      <h1>{book.title}</h1>
      <p className="muted">著者: {book.author}</p>
      <p className="description">{book.description}</p>
      <dl className="metadata-list">
        <div>
          <dt>評価</dt>
          <dd>{book.rating} / 5</dd>
        </div>
        <div>
          <dt>分類</dt>
          <dd>Web関連メモ</dd>
        </div>
      </dl>
    </article>
  );
}
