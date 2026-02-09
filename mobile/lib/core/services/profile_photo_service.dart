// dart:typed_data provided by foundation.dart

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';

/// Profile photo state
class ProfilePhotoState {
  final String? photoUrl;
  final Uint8List? photoBytes;
  final bool isLoading;
  final String? error;
  
  const ProfilePhotoState({
    this.photoUrl,
    this.photoBytes,
    this.isLoading = false,
    this.error,
  });
  
  ProfilePhotoState copyWith({
    String? photoUrl,
    Uint8List? photoBytes,
    bool? isLoading,
    String? error,
  }) {
    return ProfilePhotoState(
      photoUrl: photoUrl ?? this.photoUrl,
      photoBytes: photoBytes ?? this.photoBytes,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

/// Profile photo notifier
class ProfilePhotoNotifier extends StateNotifier<ProfilePhotoState> {
  final Ref _ref;
  static const String _photoUrlKey = 'profile_photo_url';
  
  ProfilePhotoNotifier(this._ref) : super(const ProfilePhotoState()) {
    _loadCachedPhoto();
  }
  
  Future<void> _loadCachedPhoto() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedUrl = prefs.getString(_photoUrlKey);
      if (cachedUrl != null) {
        state = state.copyWith(photoUrl: cachedUrl);
      }
    } catch (e) {
      debugPrint('Error loading cached photo: $e');
    }
  }
  
  /// Pick photo from camera or gallery
  Future<XFile?> pickPhoto({required ImageSource source}) async {
    try {
      final picker = ImagePicker();
      final image = await picker.pickImage(
        source: source,
        maxWidth: 512,
        maxHeight: 512,
        imageQuality: 85,
      );
      
      if (image != null) {
        // Load bytes for preview
        final bytes = await image.readAsBytes();
        state = state.copyWith(photoBytes: bytes);
      }
      
      return image;
    } catch (e) {
      state = state.copyWith(error: 'Erreur lors de la sélection de la photo');
      return null;
    }
  }
  
  /// Upload photo to server
  Future<bool> uploadPhoto(XFile file) async {
    state = state.copyWith(isLoading: true, error: null);
    
    try {
      final dio = _ref.read(dioProvider);
      
      // Read file bytes
      final bytes = await file.readAsBytes();
      
      // Create multipart request
      final formData = FormData.fromMap({
        'photo': MultipartFile.fromBytes(
          bytes,
          filename: 'profile_photo.jpg',
        ),
      });
      
      final response = await dio.post(
        '/api/mobile/profile/photo/',
        data: formData,
        options: Options(contentType: 'multipart/form-data'),
      );
      
      if (response.statusCode == 200 || response.statusCode == 201) {
        final photoUrl = response.data['photo_url'] as String?;
        
        // Cache the URL
        if (photoUrl != null) {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString(_photoUrlKey, photoUrl);
        }
        
        state = state.copyWith(
          photoUrl: photoUrl,
          isLoading: false,
        );
        return true;
      } else {
        throw Exception('Upload failed');
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Erreur lors de l\'upload de la photo',
      );
      return false;
    }
  }
  
  /// Clear photo
  Future<void> clearPhoto() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_photoUrlKey);
    } catch (e) {
      debugPrint('Error clearing photo: $e');
    }
    
    state = const ProfilePhotoState();
  }
}

/// Profile photo provider
final profilePhotoProvider = StateNotifierProvider<ProfilePhotoNotifier, ProfilePhotoState>((ref) {
  return ProfilePhotoNotifier(ref);
});

/// Profile photo picker widget
class ProfilePhotoPicker extends ConsumerWidget {
  final double size;
  final VoidCallback? onPhotoChanged;
  
  const ProfilePhotoPicker({
    super.key,
    this.size = 100,
    this.onPhotoChanged,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final photoState = ref.watch(profilePhotoProvider);
    
    return GestureDetector(
      onTap: () => _showPhotoOptions(context, ref),
      child: Stack(
        children: [
          // Photo container
          Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.grey.shade200,
              border: Border.all(color: Colors.white, width: 3),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.1),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: ClipOval(
              child: _buildPhotoContent(photoState),
            ),
          ),
          
          // Edit badge
          Positioned(
            right: 0,
            bottom: 0,
            child: Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: Theme.of(context).primaryColor,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 2),
              ),
              child: Icon(
                Icons.camera_alt,
                color: Colors.white,
                size: size * 0.18,
              ),
            ),
          ),
          
          // Loading overlay
          if (photoState.isLoading)
            Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.black.withValues(alpha: 0.5),
              ),
              child: const Center(
                child: CircularProgressIndicator(
                  color: Colors.white,
                  strokeWidth: 2,
                ),
              ),
            ),
        ],
      ),
    );
  }
  
  Widget _buildPhotoContent(ProfilePhotoState photoState) {
    // Show local bytes first (preview before upload)
    if (photoState.photoBytes != null) {
      return Image.memory(
        photoState.photoBytes!,
        fit: BoxFit.cover,
        width: size,
        height: size,
      );
    }
    
    // Show network image
    if (photoState.photoUrl != null) {
      return Image.network(
        photoState.photoUrl!,
        fit: BoxFit.cover,
        width: size,
        height: size,
        errorBuilder: (_, __, ___) => _buildPlaceholder(),
      );
    }
    
    // Placeholder
    return _buildPlaceholder();
  }
  
  Widget _buildPlaceholder() {
    return Icon(
      Icons.person,
      size: size * 0.5,
      color: Colors.grey.shade400,
    );
  }
  
  void _showPhotoOptions(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        padding: const EdgeInsets.all(20),
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'Changer la photo',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 20),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.camera_alt, color: Colors.blue),
                ),
                title: const Text('Prendre une photo'),
                onTap: () async {
                  Navigator.pop(context);
                  final file = await ref.read(profilePhotoProvider.notifier)
                      .pickPhoto(source: ImageSource.camera);
                  if (file != null) {
                    await ref.read(profilePhotoProvider.notifier).uploadPhoto(file);
                    onPhotoChanged?.call();
                  }
                },
              ),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.purple.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.photo_library, color: Colors.purple),
                ),
                title: const Text('Choisir dans la galerie'),
                onTap: () async {
                  Navigator.pop(context);
                  final file = await ref.read(profilePhotoProvider.notifier)
                      .pickPhoto(source: ImageSource.gallery);
                  if (file != null) {
                    await ref.read(profilePhotoProvider.notifier).uploadPhoto(file);
                    onPhotoChanged?.call();
                  }
                },
              ),
              if (ref.read(profilePhotoProvider).photoUrl != null)
                ListTile(
                  leading: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.delete, color: Colors.red),
                  ),
                  title: const Text('Supprimer la photo'),
                  onTap: () {
                    Navigator.pop(context);
                    ref.read(profilePhotoProvider.notifier).clearPhoto();
                    onPhotoChanged?.call();
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }
}
