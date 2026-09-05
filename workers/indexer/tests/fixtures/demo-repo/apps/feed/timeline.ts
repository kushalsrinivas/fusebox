// User home timeline: fetch + rank. Known slow on large follow graphs.
export interface Post {
  id: string;
  author: string;
  likes: number;
}

export async function getTimeline(userId: string, limit = 20): Promise<Post[]> {
  const posts = await fetchPosts(userId, limit * 5);
  return rankFeed(posts).slice(0, limit);
}

export function rankFeed(posts: Post[]): Post[] {
  return [...posts].sort((a, b) => b.likes - a.likes);
}

async function fetchPosts(userId: string, n: number): Promise<Post[]> {
  return [];
}
