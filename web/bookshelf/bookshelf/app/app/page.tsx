import Link from "next/link";

export default function Home() {
  return (
    <section className="hero">
      <p className="eyebrow">小さな書評ページ</p>
      <h1>本棚のホームページ</h1>
      <p>
        読んだ本の短い感想をまとめています。気になる本があれば一覧から詳細を見てください。
      </p>
      <Link href="/books" className="button-link">
        書籍一覧へ
      </Link>
    </section>
  );
}
