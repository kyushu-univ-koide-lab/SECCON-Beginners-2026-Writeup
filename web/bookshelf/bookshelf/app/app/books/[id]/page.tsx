import Link from "next/link";
import { notFound } from "next/navigation";
import BookDetail, { type Book } from "./BookDetail";

export const dynamic = "force-dynamic";

const books: Book[] = [
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
    internalNote: process.env.FLAG ?? "ctf4b{dummy_flag}",
  },
  {
    id: "3",
    title: "HTTP Field Guide",
    author: "Carol",
    description: "A small book about requests and responses.",
    rating: 3,
  },
];

type BookPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function BookPage({ params }: BookPageProps) {
  const { id } = await params;
  const book = books.find((item) => item.id === id);

  if (!book) {
    notFound();
  }

  return (
    <section>
      <Link href="/books" className="back-link">
        書籍一覧に戻る
      </Link>
      <BookDetail book={book} />
    </section>
  );
}
