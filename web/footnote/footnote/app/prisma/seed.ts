import { randomBytes } from "node:crypto";
import { createPrismaClient } from "../src/db.js";

const prisma = createPrismaClient();

function getSecretMemo() {
  const configured = process.env.SECRET_MEMO;

  if (configured === undefined || configured === "") {
    return randomBytes(6).toString("hex");
  }

  if (!/^[0-9a-f]{12}$/.test(configured)) {
    throw new Error("SECRET_MEMO must be 12 lowercase hex characters");
  }

  return configured;
}

const secretMemo = getSecretMemo();

async function main() {
  const admin = await prisma.user.upsert({
    where: { name: "admin" },
    update: { role: "admin" },
    create: { name: "admin", role: "admin" },
  });

  const editor = await prisma.user.upsert({
    where: { name: "editor" },
    update: { role: "editor" },
    create: { name: "editor", role: "editor" },
  });

  await prisma.profile.upsert({
    where: { userId: admin.id },
    update: {
      displayName: "admin",
      bio: "編集長。記事の裏側にある小さなメモを管理している。",
      secretMemo,
    },
    create: {
      displayName: "admin",
      bio: "編集長。記事の裏側にある小さなメモを管理している。",
      secretMemo,
      userId: admin.id,
    },
  });

  await prisma.profile.upsert({
    where: { userId: editor.id },
    update: {
      displayName: "佐藤みお",
      bio: "街角の小さな話を集めている編集者。",
      secretMemo: "来月の特集案: 夕方の商店街",
    },
    create: {
      displayName: "佐藤みお",
      bio: "街角の小さな話を集めている編集者。",
      secretMemo: "来月の特集案: 夕方の商店街",
      userId: editor.id,
    },
  });

  const articles = [
    {
      title: "朝の図書室から",
      body: "開館前の図書室には、まだ誰の足音もありません。窓際の机に光が差し込み、昨日返された本の背表紙だけが静かに並んでいます。棚を整えていると、誰かが挟んだ古いしおりが見つかりました。",
      authorId: admin.id,
    },
    {
      title: "商店街の雨宿り",
      body: "急な雨に降られて、古い文房具店の軒下でしばらく立ち止まりました。店主は何も言わずにタオルを差し出し、店内のラジオからは昔の天気予報が流れていました。",
      authorId: editor.id,
    },
    {
      title: "駅前ベンチ観察記",
      body: "夕方の駅前ベンチには、毎日違う物語が座っています。部活帰りの学生、買い物袋を抱えた人、待ち合わせに少し早く着いた人。五分だけ眺めると、街の速度が少し分かります。",
      authorId: editor.id,
    },
    {
      title: "古い掲示板の手紙",
      body: "公民館の入口にある掲示板には、何年も変わらない画鋲の跡があります。新しいお知らせの隅に残った日焼けの形を見ると、ここで何度も季節が入れ替わったことが分かります。",
      authorId: admin.id,
    },
    {
      title: "夜更けの編集後記",
      body: "締切前の編集室では、湯気の消えたお茶と赤いペンだけが机の上に残ります。文章を一行削るたびに、伝えたいことが少しだけ輪郭を取り戻していきます。",
      authorId: editor.id,
    },
  ];

  for (const article of articles) {
    await prisma.article.upsert({
      where: { title: article.title },
      update: {
        body: article.body,
        published: true,
        authorId: article.authorId,
      },
      create: {
        title: article.title,
        body: article.body,
        published: true,
        authorId: article.authorId,
      },
    });
  }

  await prisma.article.upsert({
    where: { title: "Unpublished Editorial Checklist" },
    update: {
      body: "Internal checklist for the next release.",
      published: false,
      authorId: admin.id,
    },
    create: {
      title: "Unpublished Editorial Checklist",
      body: "Internal checklist for the next release.",
      published: false,
      authorId: admin.id,
    },
  });
}

main()
  .finally(async () => {
    await prisma.$disconnect();
  })
  .catch(async (error) => {
    console.error(error);
    process.exit(1);
  });
