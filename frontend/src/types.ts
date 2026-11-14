export interface User {
  id: string;
  username: string;
  email: string;
  bio: string | null;
  avatar_key: string | null;
  is_private: boolean;
  status: string;
  created_at: string;
}

export interface PublicProfile {
  username: string;
  bio: string | null;
  avatar_key: string | null;
  is_private: boolean;
  created_at: string;
}

export interface PostImage {
  position: number;
  url: string;
}

export interface Post {
  id: string;
  user_id: string;
  username: string;
  user_avatar: string | null;
  caption: string | null;
  post_img_url: PostImage[];
  created_at: string;
  is_private: boolean;
  is_deleted: boolean;
}

export interface Page<T> {
  posts: T[];
  limit: number;
  next_cursor: string | null;
}

export interface FollowRelationship {
  follower_id: string;
  following_id: string;
  status: "pending" | "accepted";
  created_at: string;
}

export interface FollowStatus {
  username: string;
  status: "pending" | "accepted" | null;
  is_following: boolean;
  request_pending: boolean;
}

export interface FollowCounts {
  followers: number;
  following: number;
}

export interface TokenResponse {
  token_type: "bearer";
  access_token: string;
  expires_in: number;
  refresh_token: string;
  user: User;
}

export interface ApiError {
  detail?: string | { msg?: string }[];
}
